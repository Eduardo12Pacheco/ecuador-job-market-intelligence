"""Pruebas offline de la ruta de captura acotada de una sola página (opt-in).

``HimalayaAdapter.collect_and_persist_page`` debe realizar exactamente una
petición ``httpx`` GET a ``ENDPOINT`` con ``limit=20&offset=0``, reutilizar el
analizador existente y la construcción de ``RawPage`` (conservando los bytes
exactos de la respuesta), y persistir exactamente una página cruda más su
manifiesto a través de ``LocalCaptureStore`` con ``complete=False`` y la
advertencia de captura acotada de una sola página. Nunca debe paginar,
reintentar ni llamar a ``/jobs/api/search``, y debe fallar de forma cerrada
antes de cualquier escritura.

Todas las pruebas se ejecutan contra ``httpx.MockTransport`` y escriben solo
bajo ``tmp_path`` de pytest (el directorio de trabajo se mueve allí), de modo
que no se crea ni modifica ningún dato del repositorio.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from pathlib import Path

import httpx
import pytest
from conftest import (
    BROWSE_ENDPOINT,
    BROWSE_FIXTURE_SHA256,
    BROWSE_METADATA_JSON,
    FIXED_CAPTURED_AT,
    encode,
    make_page,
)

from job_market_intelligence.ingestion.adapter import (
    ADAPTER_VERSION,
    ATTRIBUTION_URL,
    BOUNDED_SINGLE_PAGE_WARNING,
    DEFAULT_LIMIT,
    ENDPOINT,
    HimalayaAdapter,
    PageCaptureResult,
)
from job_market_intelligence.ingestion.errors import (
    HimalayasHttpError,
    MalformedResponseError,
    PaginationError,
)
from job_market_intelligence.ingestion.models import RawPage, RunStatus
from job_market_intelligence.ingestion.parser import SOURCE
from job_market_intelligence.ingestion.storage import (
    CaptureResult,
    LocalCaptureStore,
    OverwriteError,
)

UTC = UTC

# Contrato de ruta determinista compartido con test_storage.py: componente de
# endpoint legible + sha256(endpoint)[:12] estable + offset rellenado con ceros.
ENDPOINT_HASH = hashlib.sha256(BROWSE_ENDPOINT.encode("utf-8")).hexdigest()[:12]
EXPECTED_RAW_RELATIVE = f"data/raw/himalayas/jobs_api_{ENDPOINT_HASH}/00000000.json"
EXPECTED_MANIFEST_RELATIVE = f"data/manifests/himalayas/jobs_api_{ENDPOINT_HASH}/00000000.manifest.json"

FIXED_CAPTURED_AT_ISO = "2026-08-02T17:03:28.193510+00:00"


def make_bounded_adapter(handler: object) -> tuple[HimalayaAdapter, httpx.Client]:
    """Adaptador con reloj inyectable y el manejador MockTransport dado."""
    client = httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    adapter = HimalayaAdapter(client=client, clock=lambda: FIXED_CAPTURED_AT)
    return adapter, client


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def no_output_under(tmp_path: Path) -> None:
    assert not (tmp_path / "data").exists()


class TestSinglePageCapture:
    def test_exactly_one_request_with_limit_20_offset_0(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            assert not requests, "la captura acotada nunca debe emitir una segunda petición"
            requests.append(request)
            # totalCount=45 > 20 devueltos: un llamador que pagine necesitaría la página 2.
            return httpx.Response(
                200, content=encode(make_page(0, 20, 45)), headers={"content-type": "application/json"}
            )

        adapter, client = make_bounded_adapter(handler)
        result = adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert len(requests) == 1
        assert requests[0].url.path == "/jobs/api"  # never /jobs/api/search
        assert str(requests[0].url).startswith(ENDPOINT)
        assert dict(requests[0].url.params) == {"limit": "20", "offset": "0"}
        assert result.page.offset == 0
        assert result.page.job_count == 20
        assert result.page.total_count == 45

    def test_exact_bytes_preserved_and_sha_consistent(self, tmp_path, monkeypatch, browse_fixture_bytes: bytes) -> None:
        monkeypatch.chdir(tmp_path)
        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(
                200, content=browse_fixture_bytes, headers={"content-type": "application/json"}
            )
        )
        result = adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert result.page.body == browse_fixture_bytes
        assert result.page.sha256 == hashlib.sha256(browse_fixture_bytes).hexdigest()
        assert result.capture.raw_sha256 == result.page.sha256
        assert result.capture.raw_file_path.read_bytes() == browse_fixture_bytes
        manifest = read_manifest(result.capture.manifest_path)
        assert manifest["raw_sha256"] == result.page.sha256
        assert manifest["raw_file_path"] == result.capture.raw_file_path_relative

    def test_manifest_is_partial_with_bounded_warning(self, tmp_path, monkeypatch, browse_fixture_bytes: bytes) -> None:
        monkeypatch.chdir(tmp_path)
        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(
                200, content=browse_fixture_bytes, headers={"content-type": "application/json"}
            )
        )
        result = adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        manifest = read_manifest(result.capture.manifest_path)
        assert manifest["complete"] is False
        assert manifest["warnings"] == [BOUNDED_SINGLE_PAGE_WARNING]
        assert manifest["errors"] == []

    def test_manifest_records_full_request_and_response_envelope(
        self, tmp_path, monkeypatch, browse_fixture_bytes: bytes
    ) -> None:
        monkeypatch.chdir(tmp_path)
        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(
                200, content=browse_fixture_bytes, headers={"content-type": "application/json"}
            )
        )
        result = adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        manifest = read_manifest(result.capture.manifest_path)
        metadata = json.loads(BROWSE_METADATA_JSON.read_text(encoding="utf-8"))
        assert manifest["source"] == SOURCE == "himalayas"
        assert manifest["endpoint"] == ENDPOINT == BROWSE_ENDPOINT
        assert manifest["request_params"] == {"limit": DEFAULT_LIMIT, "offset": 0}
        assert manifest["limit"] == DEFAULT_LIMIT
        assert manifest["offset"] == 0
        assert manifest["http_status"] == 200
        assert manifest["content_type"] == "application/json"
        assert manifest["captured_at"] == FIXED_CAPTURED_AT_ISO
        assert manifest["updated_at_raw"] == metadata["source_updated_at_raw"] == 1785649720
        assert manifest["updated_at_utc"] == metadata["source_updated_at_utc"] == "2026-08-02T05:48:40+00:00"
        assert manifest["timestamp_unit"] == "unix_seconds"
        assert manifest["total_count"] == metadata["total_count"] == 94542
        assert manifest["returned_jobs"] == metadata["returned_jobs"] == 20
        assert manifest["raw_file_path"] == EXPECTED_RAW_RELATIVE
        assert manifest["raw_sha256"] == BROWSE_FIXTURE_SHA256
        assert manifest["adapter_version"] == ADAPTER_VERSION == "0.1.0"
        assert manifest["attribution_url"] == ATTRIBUTION_URL == "https://himalayas.app"

    def test_result_carries_typed_report_data(self, tmp_path, monkeypatch, browse_fixture_bytes: bytes) -> None:
        monkeypatch.chdir(tmp_path)
        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(
                200, content=browse_fixture_bytes, headers={"content-type": "application/json"}
            )
        )
        result = adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert isinstance(result, PageCaptureResult)
        assert isinstance(result.page, RawPage)
        assert isinstance(result.capture, CaptureResult)
        assert result.source == SOURCE
        assert result.endpoint == ENDPOINT
        assert result.adapter_version == ADAPTER_VERSION
        assert result.attribution_url == ATTRIBUTION_URL
        assert result.run_status is RunStatus.PARTIAL
        assert result.warning == BOUNDED_SINGLE_PAGE_WARNING
        assert result.page.request_params == {"limit": DEFAULT_LIMIT, "offset": 0}
        assert result.page.captured_at == FIXED_CAPTURED_AT
        assert result.capture.raw_file_path_relative == EXPECTED_RAW_RELATIVE
        assert result.capture.manifest_file_path_relative == EXPECTED_MANIFEST_RELATIVE
        assert result.capture.raw_file_path.exists()
        assert result.capture.manifest_path.exists()

    def test_deterministic_paths_and_capture_id(self, tmp_path, monkeypatch, browse_fixture_bytes: bytes) -> None:
        monkeypatch.chdir(tmp_path)
        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(
                200, content=browse_fixture_bytes, headers={"content-type": "application/json"}
            )
        )
        result = adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert result.capture.capture_id == f"cap_{BROWSE_FIXTURE_SHA256[:16]}"
        assert result.capture.raw_file_path.name == "00000000.json"
        assert result.capture.manifest_path.name == "00000000.manifest.json"


class TestFailClosed:
    def test_non_2xx_fails_with_single_request_and_no_output(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(500, content=b"boom")

        adapter, client = make_bounded_adapter(handler)
        with pytest.raises(HimalayasHttpError) as exc_info:
            adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert "500" in str(exc_info.value)
        assert len(calls) == 1
        no_output_under(tmp_path)

    def test_transport_error_fails_without_retry_and_no_output(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            raise httpx.ConnectError("simulated connection failure")

        adapter, client = make_bounded_adapter(handler)
        with pytest.raises(HimalayasHttpError):
            adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert len(calls) == 1
        no_output_under(tmp_path)

    def test_invalid_json_fails_without_retry_and_no_output(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, content=b"this is not json", headers={"content-type": "application/json"})

        adapter, client = make_bounded_adapter(handler)
        with pytest.raises(MalformedResponseError):
            adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        assert len(calls) == 1
        no_output_under(tmp_path)

    def test_offset_mismatch_fails_closed_with_no_output(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        payload = make_page(0, 20, 20)
        payload["offset"] = 5

        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(200, content=encode(payload), headers={"content-type": "application/json"})
        )
        with pytest.raises(PaginationError):
            adapter.collect_and_persist_page(store=LocalCaptureStore())
        client.close()

        no_output_under(tmp_path)

    def test_invalid_store_rejected_before_any_request(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(200, content=b"{}")

        adapter, client = make_bounded_adapter(handler)
        with pytest.raises(TypeError):
            adapter.collect_and_persist_page(store=None)  # type: ignore[arg-type]
        client.close()

        assert calls == []
        no_output_under(tmp_path)

    def test_repeated_capture_of_same_key_is_rejected(self, tmp_path, monkeypatch, browse_fixture_bytes: bytes) -> None:
        monkeypatch.chdir(tmp_path)
        adapter, client = make_bounded_adapter(
            lambda request: httpx.Response(
                200, content=browse_fixture_bytes, headers={"content-type": "application/json"}
            )
        )
        store = LocalCaptureStore()
        first = adapter.collect_and_persist_page(store=store)
        with pytest.raises(OverwriteError):
            adapter.collect_and_persist_page(store=store)
        client.close()

        assert first.capture.raw_file_path.read_bytes() == browse_fixture_bytes
