"""Pruebas de extremo a extremo del adaptador, totalmente offline vía ``httpx.MockTransport``.

Las pruebas con accesorios reales se ejecutan contra
``data/sample/himalayas_browse_page_1.json``, página 1 del endpoint de feed
completo ``/jobs/api``. El accesorio exploratorio ``/jobs/api/search`` sigue
cubierto en ``test_parser.py``.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import fields
from datetime import UTC, datetime

import httpx
import pytest
from conftest import FIXED_CAPTURED_AT, default_job, encode, make_adapter, make_page, transport_for

from job_market_intelligence.ingestion.adapter import (
    DEFAULT_LIMIT,
    ENDPOINT,
    HimalayaAdapter,
)
from job_market_intelligence.ingestion.errors import (
    HimalayasHttpError,
    MalformedResponseError,
    PaginationError,
    TimestampError,
)
from job_market_intelligence.ingestion.models import (
    CanonicalJob,
    LocationScope,
    ObservationStatus,
    RunStatus,
)

TOTAL_45_PAGES = {
    0: make_page(0, 20, 45),
    20: make_page(20, 20, 45),
    40: make_page(40, 5, 45),
}


class TestPagination:
    def test_paginates_offsets_and_stops_at_total_count(self) -> None:
        requested = []

        def recording_handler(request: httpx.Request) -> httpx.Response:
            offset = int(request.url.params.get("offset", 0))
            requested.append((int(request.url.params["limit"]), offset))
            page = TOTAL_45_PAGES[offset]
            return httpx.Response(200, content=encode(page), headers={"content-type": "application/json"})

        adapter = HimalayaAdapter(
            client=httpx.Client(transport=httpx.MockTransport(recording_handler)),
            clock=lambda: FIXED_CAPTURED_AT,
        )
        snapshot = adapter.collect_complete_feed()

        assert requested == [(20, 0), (20, 20), (20, 40)]
        assert snapshot.page_count == 3
        assert snapshot.job_count == 45
        assert snapshot.canonical_job_count == 45
        assert snapshot.total_count == 45
        assert snapshot.run_status is RunStatus.COMPLETE
        assert len(snapshot.raw_page_sha256) == 3
        assert snapshot.http_status == 200
        assert snapshot.content_type == "application/json"
        assert snapshot.endpoint == ENDPOINT
        assert snapshot.request_params == {"limit": 20, "offset": 40}
        assert len(snapshot.raw_pages) == 3
        adapter.close()

    def test_stops_immediately_when_total_count_is_covered(self) -> None:
        pages = {0: make_page(0, 20, 20)}
        adapter, client = make_adapter(pages)
        snapshot = adapter.collect_complete_feed()
        assert snapshot.page_count == 1
        assert snapshot.job_count == 20
        assert snapshot.run_status is RunStatus.COMPLETE
        client.close()

    def test_adapter_supports_transport_injection(self) -> None:
        adapter = HimalayaAdapter(
            transport=transport_for({0: make_page(0, 20, 20)}),
            clock=lambda: FIXED_CAPTURED_AT,
        )
        snapshot = adapter.collect_complete_feed()
        assert snapshot.page_count == 1
        assert snapshot.run_status is RunStatus.COMPLETE
        adapter.close()

    def test_no_http_until_explicitly_invoked(self) -> None:
        calls = []

        def counting_handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url)
            return httpx.Response(
                200, content=encode(make_page(0, 20, 20)), headers={"content-type": "application/json"}
            )

        adapter = HimalayaAdapter(
            client=httpx.Client(transport=httpx.MockTransport(counting_handler)),
            clock=lambda: FIXED_CAPTURED_AT,
        )
        assert calls == []
        adapter.collect_complete_feed()
        assert len(calls) == 1
        adapter.close()

    def test_limit_validation(self) -> None:
        adapter, client = make_adapter({0: make_page(0, 20, 20)})
        for bad in (0, -1, 21, 100, "20"):
            with pytest.raises(ValueError):
                adapter.collect_complete_feed(limit=bad)
        assert adapter.collect_complete_feed(limit=DEFAULT_LIMIT).run_status is RunStatus.COMPLETE
        client.close()


class TestRawEvidence:
    def test_preserves_exact_raw_bytes_and_sha256(self, browse_fixture_payload: dict) -> None:
        trimmed = dict(browse_fixture_payload)
        trimmed["totalCount"] = 20
        raw_bytes = encode(trimmed)
        adapter, client = make_adapter({0: raw_bytes})
        snapshot = adapter.collect_complete_feed()

        page = snapshot.raw_pages[0]
        assert page.body == raw_bytes
        assert page.sha256 == hashlib.sha256(raw_bytes).hexdigest()
        assert snapshot.raw_page_sha256 == [page.sha256]
        assert page.status_code == 200
        assert page.content_type == "application/json"
        assert page.request_params == {"limit": 20, "offset": 0}
        assert page.updated_at_raw == trimmed["updatedAt"]
        assert page.total_count == 20
        assert page.job_count == 20
        assert snapshot.run_status is RunStatus.COMPLETE
        client.close()

    def test_fixture_page_through_adapter(self, browse_fixture_payload: dict) -> None:
        trimmed = dict(browse_fixture_payload)
        trimmed["totalCount"] = 20
        adapter, client = make_adapter({0: encode(trimmed)})
        snapshot = adapter.collect_complete_feed()

        assert snapshot.job_count == 20
        assert snapshot.canonical_job_count == 20
        assert snapshot.run_status is RunStatus.COMPLETE
        scope_counts = Counter(job.location_scope for job in snapshot.jobs)
        assert dict(scope_counts) == {
            LocationScope.WORLDWIDE: 12,
            LocationScope.OTHER_COUNTRY: 8,
        }
        assert snapshot.jobs[0].source_id == browse_fixture_payload["jobs"][0]["guid"]
        assert snapshot.jobs[1].source_id == browse_fixture_payload["jobs"][1]["guid"]
        client.close()

    def test_updated_at_is_snapshot_level_only(self, browse_fixture_payload: dict) -> None:
        trimmed = dict(browse_fixture_payload)
        trimmed["totalCount"] = 20
        adapter, client = make_adapter({0: encode(trimmed)})
        snapshot = adapter.collect_complete_feed()

        assert snapshot.api_updated_at_raw == 1785649720
        assert snapshot.api_updated_at_utc == datetime(2026, 8, 2, 5, 48, 40, tzinfo=UTC)
        names = {field.name for field in fields(CanonicalJob)}
        assert not any("updated_at" in name for name in names)
        client.close()


class TestBrowseFeed:
    """Cobertura de que el accesorio de exploración capturado ejercita el endpoint y la forma reales del feed."""

    def test_browse_fixture_endpoint_and_shape_are_covered(self, browse_fixture_payload: dict) -> None:
        trimmed = dict(browse_fixture_payload)
        trimmed["totalCount"] = 20
        adapter, client = make_adapter({0: encode(trimmed)})
        snapshot = adapter.collect_complete_feed()
        page = snapshot.raw_pages[0]

        assert snapshot.endpoint == ENDPOINT == "https://himalayas.app/jobs/api"
        assert page.request_params == {"limit": 20, "offset": 0}
        assert snapshot.request_params == {"limit": 20, "offset": 0}
        assert page.offset == 0
        assert page.job_count == 20
        assert snapshot.total_count == 20  # recortado para que la ejecución offline solo necesite la página 1
        assert snapshot.content_type == "application/json"
        assert page.updated_at_raw == 1785649720
        client.close()


class TestFailures:
    def test_non_2xx_response_fails(self) -> None:
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500, content=b"boom")))
        adapter = HimalayaAdapter(client=client, clock=lambda: FIXED_CAPTURED_AT)
        with pytest.raises(HimalayasHttpError) as exc_info:
            adapter.collect_complete_feed()
        assert "500" in str(exc_info.value)
        assert exc_info.value.snapshot is None
        client.close()

    def test_malformed_json_fails(self) -> None:
        adapter, client = make_adapter({0: b"this is not json"})
        with pytest.raises(MalformedResponseError):
            adapter.collect_complete_feed()
        client.close()

    def test_malformed_shape_fails(self) -> None:
        for broken in (
            b"[]",
            encode({"jobs": "nope", "updatedAt": 1785529437, "offset": 0, "limit": 20, "totalCount": 5}),
            encode({"jobs": [], "updatedAt": 1785529437, "offset": 0, "limit": 20}),
        ):
            adapter, client = make_adapter({0: broken})
            with pytest.raises(MalformedResponseError):
                adapter.collect_complete_feed()
            client.close()

    def test_implausible_snapshot_timestamp_fails(self) -> None:
        adapter, client = make_adapter({0: encode(make_page(0, 20, 20, updated_at=5))})
        with pytest.raises(TimestampError) as exc_info:
            adapter.collect_complete_feed()
        assert exc_info.value.snapshot is None
        client.close()

    def test_repeated_page_signature_fails_as_partial(self) -> None:
        same = encode(make_page(0, 20, 40))
        adapter, client = make_adapter({0: same, 20: same})
        with pytest.raises(PaginationError) as exc_info:
            adapter.collect_complete_feed()
        assert exc_info.value.snapshot is not None
        assert exc_info.value.snapshot.run_status is RunStatus.PARTIAL
        assert exc_info.value.snapshot.page_count == 1
        client.close()

    def test_non_advancing_page_fails(self) -> None:
        adapter, client = make_adapter({0: encode(make_page(0, 0, 40))})
        with pytest.raises(PaginationError):
            adapter.collect_complete_feed()
        client.close()

    def test_offset_mismatch_fails(self) -> None:
        payload = make_page(0, 20, 20)
        payload["offset"] = 5
        adapter, client = make_adapter({0: encode(payload)})
        with pytest.raises(PaginationError):
            adapter.collect_complete_feed()
        client.close()


class TestDuplicatesAndQuality:
    def test_duplicate_guids_collapse_while_keeping_observations(self) -> None:
        shared_guid = "https://himalayas.app/companies/acme/jobs/dup-1"
        jobs = [
            default_job(0, 0, guid=shared_guid, applicationLink=shared_guid, title="First"),
            default_job(0, 1, guid=shared_guid, applicationLink=shared_guid, title="Second"),
        ]
        adapter, client = make_adapter({0: encode(make_page(0, 2, 2, jobs=jobs))})
        snapshot = adapter.collect_complete_feed()

        assert snapshot.job_count == 2  # las observaciones crudas se conservan
        assert snapshot.canonical_job_count == 1
        assert snapshot.duplicate_guid_count == 1
        assert snapshot.run_status is RunStatus.COMPLETE
        record = snapshot.jobs[0]
        assert record.source_id == shared_guid
        assert record.title_raw == "First"  # gana la primera ocurrencia
        assert "duplicate_guid" in record.quality_flags
        client.close()

    def test_missing_guid_marks_snapshot_partial(self) -> None:
        jobs = [default_job(0, 0, guid=None, applicationLink="https://himalayas.app/companies/x/jobs/1")]
        adapter, client = make_adapter({0: encode(make_page(0, 1, 1, jobs=jobs))})
        snapshot = adapter.collect_complete_feed()

        assert snapshot.run_status is RunStatus.PARTIAL
        assert snapshot.page_count == 1  # la evidencia cruda exitosa se conserva
        assert snapshot.canonical_job_count == 1
        record = snapshot.jobs[0]
        assert record.observation_status is ObservationStatus.INVALID
        assert "missing_guid" in record.quality_flags
        client.close()

    def test_duplicate_guids_across_pages_collapse(self) -> None:
        shared = "https://himalayas.app/companies/acme/jobs/cross-page"
        page0 = make_page(0, 1, 2, jobs=[default_job(0, 0, guid=shared, applicationLink=shared)])
        page1 = make_page(1, 1, 2, jobs=[default_job(1, 1, guid=shared, applicationLink=shared)])
        adapter, client = make_adapter({0: encode(page0), 1: encode(page1)})
        snapshot = adapter.collect_complete_feed()
        assert snapshot.job_count == 2
        assert snapshot.canonical_job_count == 1
        assert snapshot.duplicate_guid_count == 1
        assert snapshot.jobs[0].quality_flags == ["duplicate_guid"]
        client.close()

    def test_client_and_transport_conflict_is_rejected(self) -> None:
        client = httpx.Client(transport=transport_for({0: make_page(0, 20, 20)}))
        with pytest.raises(ValueError):
            HimalayaAdapter(client=client, transport=transport_for({0: make_page(0, 20, 20)}))
        client.close()

    def test_zero_total_count_is_complete_empty_run(self) -> None:
        adapter, client = make_adapter({0: encode(make_page(0, 0, 0))})
        snapshot = adapter.collect_complete_feed()
        assert snapshot.run_status is RunStatus.COMPLETE
        assert snapshot.job_count == 0
        assert snapshot.canonical_job_count == 0
        assert snapshot.total_count == 0
        client.close()

    def test_changed_total_count_is_quality_event_not_failure(self) -> None:
        pages = {
            0: make_page(0, 20, 40),
            20: make_page(20, 20, 35),
        }
        adapter, client = make_adapter(pages)
        snapshot = adapter.collect_complete_feed()
        assert snapshot.run_status is RunStatus.COMPLETE
        assert "total_count_changed" in snapshot.quality_flags
        client.close()

    def test_changed_api_updated_at_is_quality_event_not_failure(self) -> None:
        pages = {
            0: make_page(0, 20, 40),
            20: make_page(20, 20, 40, updated_at=1785529438),
        }
        adapter, client = make_adapter(pages)
        snapshot = adapter.collect_complete_feed()
        assert snapshot.run_status is RunStatus.COMPLETE
        assert "api_updated_at_changed" in snapshot.quality_flags
        client.close()

    def test_cross_page_timestamp_unit_divergence_is_quality_event(self) -> None:
        pages = {
            0: make_page(0, 20, 40),
            20: make_page(20, 20, 40, updated_at=1785529437000),
        }
        adapter, client = make_adapter(pages)
        snapshot = adapter.collect_complete_feed()
        assert snapshot.run_status is RunStatus.COMPLETE
        assert "timestamp_unit_divergence" in snapshot.quality_flags
        assert "api_updated_at_changed" in snapshot.quality_flags
        client.close()
