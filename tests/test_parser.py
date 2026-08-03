"""Pruebas del parser contra los accesorios offline reales y entradas malformadas.

El accesorio de navegación canónico ``data/sample/himalayas_browse_page_1.json``
es la página 1 del endpoint de feed completo ``/jobs/api`` (limit=20, offset=0).
El accesorio exploratorio ``data/sample/himalayas_ec_page_1.json`` es una página
de ``/jobs/api/search`` filtrada por Ecuador (no es una línea base de feed
completo) y se conserva solo para ejercitar las formas de parseo y
normalización del alcance Ecuador.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import fields
from datetime import datetime, timezone

import pytest

from job_market_intelligence.ingestion.adapter import ADAPTER_VERSION
from job_market_intelligence.ingestion.errors import MalformedResponseError, TimestampError
from job_market_intelligence.ingestion.models import (
    CanonicalJob,
    LocationScope,
    ObservationStatus,
    TimestampUnit,
)
from job_market_intelligence.ingestion.parser import SOURCE, canonical_id_for, parse_job, parse_page

from conftest import BROWSE_ENDPOINT, BROWSE_FIXTURE_SHA256, BROWSE_METADATA_JSON, FIXTURE_SHA256

CAPTURED_AT = datetime(2026, 8, 2, 17, 3, 28, tzinfo=timezone.utc)
FIXTURE_UPDATED_AT_UTC = datetime(2026, 7, 31, 20, 23, 57, tzinfo=timezone.utc)
# Hora de captura real del accesorio de navegación (ver su sidecar de metadatos).
BROWSE_CAPTURED_AT = datetime(2026, 8, 2, 17, 38, 6, 487596, tzinfo=timezone.utc)
BROWSE_UPDATED_AT_UTC = datetime(2026, 8, 2, 5, 48, 40, tzinfo=timezone.utc)


class TestFixtureIntegrity:
    def test_fixture_sha256_matches_metadata(self, fixture_bytes: bytes) -> None:
        assert hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256

    def test_browse_fixture_sha256_matches_metadata(self, browse_fixture_bytes: bytes) -> None:
        assert hashlib.sha256(browse_fixture_bytes).hexdigest() == BROWSE_FIXTURE_SHA256

    def test_browse_fixture_metadata_records_endpoint_and_params(self) -> None:
        metadata = json.loads(BROWSE_METADATA_JSON.read_text(encoding="utf-8"))
        assert metadata["source"] == "himalayas"
        assert metadata["endpoint"] == BROWSE_ENDPOINT == "https://himalayas.app/jobs/api"
        assert metadata["request_params"] == {"limit": 20, "offset": 0}
        assert metadata["adapter_version"] == ADAPTER_VERSION == "0.1.0"
        assert metadata["fixture_sha256"] == BROWSE_FIXTURE_SHA256
        assert metadata["http_status"] == 200
        assert metadata["content_type"] == "application/json"
        assert metadata["not_complete_feed"] is True
        assert "not a complete market snapshot" in metadata["purpose"]


class TestBrowseFixtureShape:
    """Forma y cobertura de parseo del accesorio de navegación canónico ``/jobs/api``."""

    def test_browse_page_shape(self, browse_fixture_payload: dict) -> None:
        page = parse_page(browse_fixture_payload)
        assert page.total_count == 94542
        assert page.offset == 0
        assert page.limit == 20
        assert page.updated_at_raw == 1785649720
        assert page.updated_at_utc == BROWSE_UPDATED_AT_UTC
        assert page.timestamp_unit is TimestampUnit.UNIX_SECONDS
        assert len(page.raw_jobs) == 20

    def test_browse_jobs_parse_active_without_flags(self, browse_fixture_payload: dict) -> None:
        page = parse_page(browse_fixture_payload)
        scope_counts = Counter()
        for raw in page.raw_jobs:
            job = parse_job(raw, snapshot_id="snap-browse", captured_at=BROWSE_CAPTURED_AT)
            assert job.quality_flags == []
            assert job.observation_status is ObservationStatus.ACTIVE
            scope_counts[job.location_scope] += 1
        # La página 1 del feed de navegación no contiene empleos explícitos de Ecuador; el
        # accesorio exploratorio filtrado por EC cubre esa clase.
        assert dict(scope_counts) == {
            LocationScope.WORLDWIDE: 12,
            LocationScope.OTHER_COUNTRY: 8,
        }


class TestParsePage:
    def test_fixture_page_shape(self, fixture_payload: dict) -> None:
        page = parse_page(fixture_payload)
        assert page.total_count == 405
        assert page.offset == 0
        assert page.limit == 20
        assert page.updated_at_raw == 1785529437
        assert page.updated_at_utc == FIXTURE_UPDATED_AT_UTC
        assert page.timestamp_unit is TimestampUnit.UNIX_SECONDS
        assert len(page.raw_jobs) == 20

    def test_missing_or_non_list_jobs_is_malformed(self) -> None:
        with pytest.raises(MalformedResponseError):
            parse_page({"updatedAt": 1785529437, "offset": 0, "limit": 20, "totalCount": 5})
        with pytest.raises(MalformedResponseError):
            parse_page({"updatedAt": 1785529437, "offset": 0, "limit": 20, "totalCount": 5, "jobs": "nope"})

    def test_missing_or_invalid_pagination_fields_are_malformed(self) -> None:
        for broken in [
            {"updatedAt": 1785529437, "offset": 0, "limit": 20, "jobs": []},  # totalCount ausente
            {"updatedAt": 1785529437, "offset": 0, "totalCount": 5, "jobs": []},  # limit ausente
            {"updatedAt": 1785529437, "limit": 20, "totalCount": 5, "jobs": []},  # offset ausente
            {"updatedAt": 1785529437, "offset": 0, "limit": "20", "totalCount": 5, "jobs": []},
            {"updatedAt": 1785529437, "offset": 0, "limit": 20, "totalCount": True, "jobs": []},
        ]:
            with pytest.raises(MalformedResponseError):
                parse_page(broken)

    def test_non_object_payload_is_malformed(self) -> None:
        with pytest.raises(MalformedResponseError):
            parse_page([1, 2, 3])

    def test_implausible_updated_at_is_rejected(self) -> None:
        payload = {
            "updatedAt": 5,
            "offset": 0,
            "limit": 20,
            "totalCount": 1,
            "jobs": [],
        }
        with pytest.raises(TimestampError):
            parse_page(payload)

    def test_null_updated_at_is_tolerated_as_unknown(self) -> None:
        payload = {"updatedAt": None, "offset": 0, "limit": 20, "totalCount": 0, "jobs": []}
        page = parse_page(payload)
        assert page.updated_at_raw is None
        assert page.updated_at_utc is None
        assert page.timestamp_unit is TimestampUnit.UNKNOWN


class TestParseJob:
    def test_fixture_job_canonical_projection(self, fixture_payload: dict) -> None:
        raw = fixture_payload["jobs"][0]
        job = parse_job(raw, snapshot_id="snap-1", captured_at=CAPTURED_AT)
        assert job.source == SOURCE
        assert job.source_id == raw["guid"]
        # el guid y la URL de aplicación se conservan por separado; se acepta la igualdad actual del payload.
        assert job.source_url == raw["guid"]
        assert job.application_url == raw["applicationLink"]
        assert job.source_url == job.application_url
        assert job.title_raw == raw["title"]
        assert job.company_raw == raw["companyName"]
        assert job.company_slug_raw == raw["companySlug"]
        assert job.excerpt_raw == raw["excerpt"]
        assert job.description_html_raw == raw["description"]
        assert job.location_restrictions_raw == raw["locationRestrictions"]
        assert job.location_scope is LocationScope.EXPLICIT_EC
        assert job.timezone_restrictions_raw == raw["timezoneRestrictions"]
        assert job.employment_type_raw == raw["employmentType"]
        assert job.seniority_raw == raw["seniority"]
        assert job.categories_raw == raw["categories"]
        assert job.salary_min_raw is None
        assert job.salary_period_raw == "annual"
        assert job.currency_raw == "USD"
        assert job.published_at_raw == raw["pubDate"]
        assert job.published_at_utc == datetime.fromtimestamp(raw["pubDate"], tz=timezone.utc)
        assert job.expires_at_utc == datetime.fromtimestamp(raw["expiryDate"], tz=timezone.utc)
        assert job.observation_status is ObservationStatus.ACTIVE
        assert job.quality_flags == []

    def test_fixture_job_ecuador_only(self, fixture_payload: dict) -> None:
        raw = fixture_payload["jobs"][1]
        job = parse_job(raw, snapshot_id="snap-1", captured_at=CAPTURED_AT)
        assert raw["locationRestrictions"] == ["Ecuador"]
        assert job.location_scope is LocationScope.EXPLICIT_EC

    def test_canonical_id_is_deterministic_hash(self, fixture_payload: dict) -> None:
        raw = fixture_payload["jobs"][0]
        first = parse_job(raw, snapshot_id="snap-1", captured_at=CAPTURED_AT)
        second = parse_job(raw, snapshot_id="snap-2", captured_at=CAPTURED_AT)
        assert first.canonical_id == second.canonical_id
        assert first.canonical_id == canonical_id_for(first.source_id)

    def test_missing_guid_is_invalid_record(self) -> None:
        raw = {
            "applicationLink": "https://himalayas.app/companies/x/jobs/1",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 1785529437,
            "expiryDate": 1786187742,
        }
        job = parse_job(raw, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.observation_status is ObservationStatus.INVALID
        assert "missing_guid" in job.quality_flags

    def test_missing_application_link_is_invalid(self) -> None:
        raw = {
            "guid": "g",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 1785529437,
            "expiryDate": 1786187742,
        }
        job = parse_job(raw, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.observation_status is ObservationStatus.INVALID
        assert "missing_application_link" in job.quality_flags

    def test_missing_required_text_fields_are_invalid(self) -> None:
        raw = {
            "guid": "g",
            "applicationLink": "a",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 1785529437,
            "expiryDate": 1786187742,
        }
        job = parse_job(raw, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.observation_status is ObservationStatus.INVALID
        assert {"missing_title", "missing_company", "missing_description"} <= set(job.quality_flags)

    def test_null_timestamps_are_allowed(self) -> None:
        raw = {
            "guid": "g",
            "applicationLink": "a",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": None,
            "expiryDate": None,
        }
        job = parse_job(raw, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.published_at_utc is None
        assert job.expires_at_utc is None
        assert job.observation_status is ObservationStatus.ACTIVE

    def test_implausible_job_timestamp_is_invalid(self) -> None:
        raw = {
            "guid": "g",
            "applicationLink": "a",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 5,
            "expiryDate": 1786187742,
        }
        job = parse_job(raw, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.observation_status is ObservationStatus.INVALID
        assert "implausible_timestamp:pubDate" in job.quality_flags
        assert job.published_at_utc is None

    def test_timestamp_unit_divergence_is_flagged(self) -> None:
        raw = {
            "guid": "g",
            "applicationLink": "a",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 1785529437000,  # milisegundos mientras que la página usa segundos
            "expiryDate": 1786187742,
        }
        job = parse_job(
            raw,
            snapshot_id="snap",
            captured_at=CAPTURED_AT,
            expected_unit=TimestampUnit.UNIX_SECONDS,
        )
        assert job.published_at_utc == datetime.fromtimestamp(1785529437, tz=timezone.utc)
        assert "timestamp_unit_divergence:pubDate" in job.quality_flags

    def test_expired_observation(self) -> None:
        raw = {
            "guid": "g",
            "applicationLink": "a",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 1780000000,
            "expiryDate": 1780000000,  # 2026-05-29, antes de captured_at
        }
        job = parse_job(raw, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.observation_status is ObservationStatus.EXPIRED

    def test_non_dict_entry_is_missing_observation(self) -> None:
        job = parse_job("not-a-dict", snapshot_id="snap", captured_at=CAPTURED_AT)
        assert job.observation_status is ObservationStatus.MISSING
        assert "malformed_job_entry" in job.quality_flags
        assert job.location_scope is LocationScope.UNKNOWN

    def test_expected_unit_unknown_skips_divergence_flag(self) -> None:
        # Una página con updatedAt nulo no tiene evidencia de unidad; las marcas de tiempo
        # de los empleos no deben marcarse por divergencia contra ella.
        raw = {
            "guid": "g",
            "applicationLink": "a",
            "title": "t",
            "companyName": "c",
            "description": "<p>d</p>",
            "locationRestrictions": ["Ecuador"],
            "pubDate": 1785529437000,
            "expiryDate": 1786187742,
        }
        job = parse_job(
            raw,
            snapshot_id="snap",
            captured_at=CAPTURED_AT,
            expected_unit=TimestampUnit.UNKNOWN,
        )
        assert not any(flag.startswith("timestamp_unit_divergence") for flag in job.quality_flags)
        assert job.published_at_utc == datetime.fromtimestamp(1785529437, tz=timezone.utc)

    def test_updated_at_is_not_a_canonical_job_field(self) -> None:
        names = {field.name for field in fields(CanonicalJob)}
        assert "api_updated_at_raw" not in names
        assert "api_updated_at_utc" not in names
        assert not any("updated_at" in name for name in names)
        # El valor a nivel de instantánea lo expone parse_page en su lugar.
        page = parse_page(
            {"updatedAt": 1785529437, "offset": 0, "limit": 20, "totalCount": 0, "jobs": []}
        )
        assert page.updated_at_raw == 1785529437
