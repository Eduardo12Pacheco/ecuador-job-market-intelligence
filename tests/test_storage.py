"""Pruebas acotadas de persistencia local de páginas crudas y manifiestos.

Totalmente offline: cada prueba escribe solo bajo el ``tmp_path`` de pytest
(el directorio de trabajo se mueve allí), así que no se crea ni modifica ningún
dato del repositorio. El accesorio de navegación canónico se reproduce a través
de :class:`LocalCaptureStore` exactamente como se capturó.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import (
    BROWSE_ENDPOINT,
    BROWSE_FIXTURE_SHA256,
    BROWSE_METADATA_JSON,
    FIXED_CAPTURED_AT,
)

from job_market_intelligence.ingestion.models import RawPage, RunStatus, TimestampUnit
from job_market_intelligence.ingestion.storage import (
    CaptureResult,
    IntegrityError,
    LocalCaptureStore,
    OverwriteError,
    StorageError,
)

# Contrato de ruta determinista: componente de endpoint legible + hash de endpoint
# estable + offset rellenado con ceros. El hash es sha256(endpoint)[:12].
BROWSE_ENDPOINT_HASH = "6b8244a52a80"
EXPECTED_RAW_RELATIVE = f"data/raw/himalayas/jobs_api_{BROWSE_ENDPOINT_HASH}/00000000.json"
EXPECTED_MANIFEST_RELATIVE = f"data/manifests/himalayas/jobs_api_{BROWSE_ENDPOINT_HASH}/00000000.manifest.json"

REQUIRED_MANIFEST_FIELDS = {
    "source",
    "endpoint",
    "request_params",
    "offset",
    "limit",
    "http_status",
    "content_type",
    "captured_at",
    "updated_at_raw",
    "timestamp_unit",
    "total_count",
    "returned_jobs",
    "raw_file_path",
    "raw_sha256",
    "adapter_version",
    "attribution_url",
    "complete",
    "warnings",
    "errors",
}

BROWSE_UPDATED_AT_UTC = datetime(2026, 8, 2, 5, 48, 40, tzinfo=UTC)
BROWSE_CAPTURED_AT = datetime(2026, 8, 2, 17, 38, 6, 487596, tzinfo=UTC)


def make_page(
    body: bytes,
    *,
    offset: int = 0,
    request_params: dict | None = None,
    status_code: int = 200,
    content_type: str | None = "application/json",
    sha256: str | None = None,
    updated_at_raw: int | str | None = 1785649720,
    updated_at_utc: datetime | None = BROWSE_UPDATED_AT_UTC,
    timestamp_unit: TimestampUnit = TimestampUnit.UNIX_SECONDS,
    total_count: int = 94542,
    job_count: int = 20,
    captured_at: datetime = FIXED_CAPTURED_AT,
) -> RawPage:
    """Construye un RawPage para los bytes del accesorio de navegación canónico."""
    if request_params is None:
        request_params = {"limit": 20, "offset": 0}
    if sha256 is None:
        sha256 = hashlib.sha256(body).hexdigest()
    return RawPage(
        body=body,
        request_params=request_params,
        status_code=status_code,
        content_type=content_type,
        sha256=sha256,
        updated_at_raw=updated_at_raw,
        updated_at_utc=updated_at_utc,
        timestamp_unit=timestamp_unit,
        total_count=total_count,
        job_count=job_count,
        offset=offset,
        captured_at=captured_at,
        run_status=RunStatus.COMPLETE,
    )


def persist_browse(
    store: LocalCaptureStore,
    page: RawPage,
    *,
    complete: bool = False,
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    capture_id: str | None = None,
) -> CaptureResult:
    return store.persist_page(
        page,
        source="himalayas",
        endpoint=BROWSE_ENDPOINT,
        attribution_url="https://himalayas.app",
        adapter_version="0.1.0",
        complete=complete,
        warnings=warnings,
        errors=errors,
        capture_id=capture_id,
    )


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestRawPersistence:
    def test_exact_bytes_round_trip(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(browse_fixture_bytes)
        result = persist_browse(LocalCaptureStore(), page)

        assert result.raw_file_path_relative == EXPECTED_RAW_RELATIVE
        raw_bytes = result.raw_file_path.read_bytes()
        assert raw_bytes == browse_fixture_bytes
        assert result.raw_file_path.read_bytes() == page.body

    def test_correct_sha256_recorded(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(browse_fixture_bytes)
        result = persist_browse(LocalCaptureStore(), page)

        assert page.sha256 == hashlib.sha256(browse_fixture_bytes).hexdigest()
        assert page.sha256 == BROWSE_FIXTURE_SHA256
        manifest = read_manifest(result.manifest_path)
        assert manifest["raw_sha256"] == BROWSE_FIXTURE_SHA256

    def test_manifest_raw_path_consistency(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes))

        manifest = read_manifest(result.manifest_path)
        assert manifest["raw_file_path"] == EXPECTED_RAW_RELATIVE
        referenced = (tmp_path / manifest["raw_file_path"]).read_bytes()
        assert referenced == browse_fixture_bytes

    def test_distinct_offsets_produce_distinct_paths(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        first = persist_browse(store, make_page(browse_fixture_bytes, offset=0))
        second = persist_browse(
            store,
            make_page(browse_fixture_bytes, offset=20, request_params={"limit": 20, "offset": 20}),
        )

        assert first.raw_file_path_relative == EXPECTED_RAW_RELATIVE
        assert second.raw_file_path_relative == (f"data/raw/himalayas/jobs_api_{BROWSE_ENDPOINT_HASH}/00000020.json")
        assert first.raw_file_path != second.raw_file_path
        assert first.manifest_path != second.manifest_path
        assert second.raw_file_path.exists()
        assert second.manifest_path.exists()

    def test_same_readable_component_distinct_hosts_do_not_collide(
        self, monkeypatch, tmp_path, browse_fixture_bytes
    ) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes)
        first = persist_browse(store, page)
        second = store.persist_page(
            page,
            source="himalayas",
            endpoint="https://other.example/jobs/api",
            attribution_url="https://himalayas.app",
            adapter_version="0.1.0",
            complete=False,
        )

        assert first.raw_file_path.parent != second.raw_file_path.parent
        assert second.raw_file_path.exists()

    def test_offset_is_zero_padded(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        result = persist_browse(store, make_page(browse_fixture_bytes, offset=7))

        assert result.raw_file_path.name == "00000007.json"
        assert result.manifest_path.name == "00000007.manifest.json"

    def test_identical_inputs_produce_identical_outputs_across_roots(
        self, monkeypatch, tmp_path, browse_fixture_bytes
    ) -> None:
        captured_outputs = []
        for sub in ("a", "b"):
            work = tmp_path / sub
            work.mkdir()
            monkeypatch.chdir(work)
            page = make_page(browse_fixture_bytes, captured_at=BROWSE_CAPTURED_AT)
            result = persist_browse(LocalCaptureStore(), page)
            captured_outputs.append(
                (
                    result.raw_file_path.read_bytes(),
                    result.manifest_path.read_bytes(),
                    result.raw_file_path_relative,
                    result.manifest_file_path_relative,
                    result.capture_id,
                )
            )

        raw_a, manifest_a, raw_rel_a, manifest_rel_a, capture_id_a = captured_outputs[0]
        raw_b, manifest_b, raw_rel_b, manifest_rel_b, capture_id_b = captured_outputs[1]
        assert raw_a == raw_b == browse_fixture_bytes
        assert manifest_a == manifest_b
        assert raw_rel_a == raw_rel_b == EXPECTED_RAW_RELATIVE
        assert manifest_rel_a == manifest_rel_b == EXPECTED_MANIFEST_RELATIVE
        assert capture_id_a == capture_id_b


class TestManifestContent:
    def test_all_required_fields_present(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes))

        manifest = read_manifest(result.manifest_path)
        assert REQUIRED_MANIFEST_FIELDS <= set(manifest)
        assert manifest["manifest_version"] == 1
        assert manifest["complete"] is False
        assert manifest["warnings"] == []
        assert manifest["errors"] == []

    def test_utc_capture_and_updated_at_serialization(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(browse_fixture_bytes, captured_at=BROWSE_CAPTURED_AT)
        result = persist_browse(LocalCaptureStore(), page)

        manifest = read_manifest(result.manifest_path)
        assert manifest["captured_at"] == "2026-08-02T17:38:06.487596+00:00"
        assert manifest["updated_at_raw"] == 1785649720
        assert manifest["updated_at_utc"] == "2026-08-02T05:48:40+00:00"
        assert manifest["timestamp_unit"] == "unix_seconds"

    def test_http_status_and_content_type_preserved_exactly(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(
            browse_fixture_bytes,
            status_code=201,
            content_type="application/json; charset=utf-8",
        )
        result = persist_browse(LocalCaptureStore(), page)

        manifest = read_manifest(result.manifest_path)
        assert manifest["http_status"] == 201
        assert manifest["content_type"] == "application/json; charset=utf-8"

    def test_manifest_matches_fixture_metadata(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        metadata = json.loads(BROWSE_METADATA_JSON.read_text(encoding="utf-8"))
        page = make_page(browse_fixture_bytes, captured_at=BROWSE_CAPTURED_AT)
        result = persist_browse(LocalCaptureStore(), page)

        manifest = read_manifest(result.manifest_path)
        assert manifest["source"] == metadata["source"] == "himalayas"
        assert manifest["endpoint"] == metadata["endpoint"] == BROWSE_ENDPOINT
        assert manifest["request_params"] == metadata["request_params"]
        assert manifest["http_status"] == metadata["http_status"] == 200
        assert manifest["content_type"] == metadata["content_type"] == "application/json"
        assert manifest["captured_at"] == metadata["captured_at"]
        assert manifest["updated_at_raw"] == metadata["source_updated_at_raw"]
        assert manifest["updated_at_utc"] == metadata["source_updated_at_utc"]
        assert manifest["timestamp_unit"] == metadata["source_updated_at_unit"]
        assert manifest["total_count"] == metadata["total_count"] == 94542
        assert manifest["returned_jobs"] == metadata["returned_jobs"] == 20
        assert manifest["raw_sha256"] == metadata["fixture_sha256"] == BROWSE_FIXTURE_SHA256
        assert manifest["adapter_version"] == metadata["adapter_version"] == "0.1.0"
        assert manifest["attribution_url"] == metadata["attribution_url"] == "https://himalayas.app"
        assert manifest["complete"] is False

    def test_limit_taken_from_request_params(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        for sub, request_params, expected in (
            ("with_limit", {"limit": 20, "offset": 0}, 20),
            ("without_limit", {"offset": 0}, None),
        ):
            work = tmp_path / sub
            work.mkdir()
            monkeypatch.chdir(work)
            page = make_page(browse_fixture_bytes, request_params=request_params)
            manifest = read_manifest(persist_browse(LocalCaptureStore(), page).manifest_path)
            assert manifest["limit"] is expected

    def test_capture_id_default_deterministic_and_explicit(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        page = make_page(browse_fixture_bytes)

        work = tmp_path / "default"
        work.mkdir()
        monkeypatch.chdir(work)
        default_result = persist_browse(LocalCaptureStore(), page)
        assert default_result.capture_id == f"cap_{BROWSE_FIXTURE_SHA256[:16]}"
        assert read_manifest(default_result.manifest_path)["capture_id"] == default_result.capture_id

        work = tmp_path / "explicit"
        work.mkdir()
        monkeypatch.chdir(work)
        explicit = persist_browse(LocalCaptureStore(), page, capture_id="run-2026-08-02-1")
        assert explicit.capture_id == "run-2026-08-02-1"
        assert read_manifest(explicit.manifest_path)["capture_id"] == "run-2026-08-02-1"

    def test_manifest_is_utf8_json(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes))

        manifest = read_manifest(result.manifest_path)
        assert isinstance(manifest, dict)
        assert result.manifest_path.read_bytes().endswith(b"\n")


class TestBoundedAndPartial:
    def test_bounded_page_with_http_200_can_be_partial(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes), complete=False)

        manifest = read_manifest(result.manifest_path)
        assert manifest["complete"] is False
        assert manifest["http_status"] == 200
        assert result.raw_file_path.exists()

    def test_complete_true_when_no_errors(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes), complete=True)

        assert read_manifest(result.manifest_path)["complete"] is True

    def test_errors_force_complete_false(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(
            LocalCaptureStore(),
            make_page(browse_fixture_bytes),
            complete=True,
            errors=("job entry 3 failed to parse",),
        )

        manifest = read_manifest(result.manifest_path)
        assert manifest["complete"] is False
        assert manifest["errors"] == ["job entry 3 failed to parse"]
        assert result.raw_file_path.exists()

    def test_warnings_recorded(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(
            LocalCaptureStore(),
            make_page(browse_fixture_bytes),
            warnings=("source_health_degraded",),
        )

        manifest = read_manifest(result.manifest_path)
        assert manifest["warnings"] == ["source_health_degraded"]
        assert manifest["complete"] is False


class TestOverwriteProtection:
    def test_repeated_persist_of_same_key_is_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes)
        first = persist_browse(store, page)

        with pytest.raises(OverwriteError):
            persist_browse(store, page)
        assert first.raw_file_path.read_bytes() == browse_fixture_bytes

    def test_existing_raw_file_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        target = tmp_path / EXPECTED_RAW_RELATIVE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"pre-existing bytes")

        with pytest.raises(OverwriteError):
            persist_browse(store, make_page(browse_fixture_bytes))
        assert target.read_bytes() == b"pre-existing bytes"
        assert not (tmp_path / EXPECTED_MANIFEST_RELATIVE).exists()

    def test_existing_manifest_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        target = tmp_path / EXPECTED_MANIFEST_RELATIVE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")

        with pytest.raises(OverwriteError):
            persist_browse(store, make_page(browse_fixture_bytes))
        assert not (tmp_path / EXPECTED_RAW_RELATIVE).exists()


class TestRejections:
    def test_non_2xx_response_rejected_with_no_files(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes, status_code=500)

        with pytest.raises(StorageError) as exc_info:
            persist_browse(store, page)
        assert "500" in str(exc_info.value)
        assert not (tmp_path / EXPECTED_RAW_RELATIVE).exists()
        assert not (tmp_path / EXPECTED_MANIFEST_RELATIVE).exists()

    def test_sha_mismatch_rejected_with_no_files(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes, sha256="0" * 64)

        with pytest.raises(IntegrityError):
            persist_browse(store, page)
        assert not (tmp_path / EXPECTED_RAW_RELATIVE).exists()
        assert not (tmp_path / EXPECTED_MANIFEST_RELATIVE).exists()

    def test_empty_sha_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes, sha256="")

        with pytest.raises(IntegrityError):
            persist_browse(store, page)

    def test_body_not_bytes_rejected(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        page = dataclasses.replace(make_page(b"ignored"), body="not bytes")

        with pytest.raises(ValueError):
            persist_browse(LocalCaptureStore(), page)

    def test_naive_captured_at_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(browse_fixture_bytes, captured_at=datetime(2026, 8, 2, 17, 3, 28))

        with pytest.raises(ValueError):
            persist_browse(LocalCaptureStore(), page)

    def test_naive_updated_at_utc_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(browse_fixture_bytes, updated_at_utc=datetime(2026, 8, 2, 5, 48, 40))

        with pytest.raises(ValueError):
            persist_browse(LocalCaptureStore(), page)

    def test_invalid_offset_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        for bad_offset in (-1, "0", None):
            page = make_page(browse_fixture_bytes, offset=bad_offset)
            with pytest.raises(ValueError):
                persist_browse(LocalCaptureStore(), page)

    def test_invalid_request_params_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        non_dict = make_page(browse_fixture_bytes, request_params=["limit", "20"])
        with pytest.raises(ValueError):
            persist_browse(LocalCaptureStore(), non_dict)

        non_serializable = make_page(browse_fixture_bytes, request_params={"limit": 20, "client": object()})
        with pytest.raises(StorageError):
            persist_browse(LocalCaptureStore(), non_serializable)
        assert not (tmp_path / EXPECTED_RAW_RELATIVE).exists()

    def test_invalid_source_or_endpoint_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes)

        for bad_source in ("", "../evil", "a/b"):
            with pytest.raises(ValueError):
                store.persist_page(
                    page,
                    source=bad_source,
                    endpoint=BROWSE_ENDPOINT,
                    attribution_url="https://himalayas.app",
                    adapter_version="0.1.0",
                )
        with pytest.raises(ValueError):
            store.persist_page(
                page,
                source="himalayas",
                endpoint="",
                attribution_url="https://himalayas.app",
                adapter_version="0.1.0",
            )


class TestManifestSafety:
    def test_secret_request_params_redacted(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(
            browse_fixture_bytes,
            request_params={
                "limit": 20,
                "offset": 0,
                "api_key": "SECRET_VALUE",
                "Authorization": "Bearer sekrit-token",
                "access_token": "tok123",
            },
        )
        result = persist_browse(LocalCaptureStore(), page)

        manifest = read_manifest(result.manifest_path)
        assert manifest["request_params"]["api_key"] == "[REDACTED]"
        assert manifest["request_params"]["Authorization"] == "[REDACTED]"
        assert manifest["request_params"]["access_token"] == "[REDACTED]"
        assert manifest["request_params"]["limit"] == 20
        assert "secret_request_params_redacted" in manifest["warnings"]

        raw_text = result.manifest_path.read_text(encoding="utf-8")
        assert "SECRET_VALUE" not in raw_text
        assert "sekrit-token" not in raw_text
        assert "tok123" not in raw_text

    def test_no_absolute_or_escaping_paths_in_manifest(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes))

        raw_text = result.manifest_path.read_text(encoding="utf-8")
        assert ".." not in raw_text
        assert str(tmp_path) not in raw_text
        manifest = read_manifest(result.manifest_path)
        assert manifest["raw_file_path"] == EXPECTED_RAW_RELATIVE
        assert not manifest["raw_file_path"].startswith("/")
        assert not manifest["raw_file_path"].startswith("\\")
        assert ":" not in manifest["raw_file_path"].split("/")[0]

    def test_manifest_contains_no_headers_or_cwd(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        result = persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes))

        raw_text = result.manifest_path.read_text(encoding="utf-8")
        assert "user-agent" not in raw_text.lower()
        assert "cookie" not in raw_text.lower()
        assert os.getcwd() not in raw_text


class TestTriangulation:
    def test_null_content_type_and_updated_at_serialize_as_null(
        self, monkeypatch, tmp_path, browse_fixture_bytes
    ) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(
            browse_fixture_bytes,
            content_type=None,
            updated_at_raw=None,
            updated_at_utc=None,
        )
        result = persist_browse(LocalCaptureStore(), page)

        manifest = read_manifest(result.manifest_path)
        assert manifest["content_type"] is None
        assert manifest["updated_at_raw"] is None
        assert manifest["updated_at_utc"] is None

    def test_run_status_stamp_does_not_change_caller_declared_complete(
        self, monkeypatch, tmp_path, browse_fixture_bytes
    ) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(browse_fixture_bytes)
        page = dataclasses.replace(page, run_status=RunStatus.PARTIAL)
        result = persist_browse(LocalCaptureStore(), page, complete=True)

        # ``complete`` es la declaración de acotación del llamador; el sello de run-status
        # del adaptador no se vuelve a leer silenciosamente aquí.
        assert read_manifest(result.manifest_path)["complete"] is True

    def test_millisecond_timestamp_unit_recorded(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        page = make_page(
            browse_fixture_bytes,
            updated_at_raw=1785529437000,
            updated_at_utc=datetime(2026, 8, 1, 0, 23, 57, tzinfo=UTC),
            timestamp_unit=TimestampUnit.UNIX_MILLISECONDS,
        )
        result = persist_browse(LocalCaptureStore(), page)

        manifest = read_manifest(result.manifest_path)
        assert manifest["updated_at_raw"] == 1785529437000
        assert manifest["timestamp_unit"] == "unix_milliseconds"

    def test_distinct_sources_do_not_collide(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes)
        first = persist_browse(store, page)
        second = store.persist_page(
            page,
            source="himalayas-archive",
            endpoint=BROWSE_ENDPOINT,
            attribution_url="https://himalayas.app",
            adapter_version="0.1.0",
            complete=False,
        )

        assert first.raw_file_path != second.raw_file_path
        assert second.raw_file_path.parent.name == f"jobs_api_{BROWSE_ENDPOINT_HASH}"
        assert second.raw_file_path.exists()

    def test_absolute_root_inside_cwd_stays_repo_relative(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore(
            raw_root=tmp_path / "data" / "raw",
            manifest_root=tmp_path / "data" / "manifests",
        )
        result = persist_browse(store, make_page(browse_fixture_bytes))

        assert result.raw_file_path_relative == EXPECTED_RAW_RELATIVE
        assert result.manifest_file_path_relative == EXPECTED_MANIFEST_RELATIVE
        manifest = read_manifest(result.manifest_path)
        assert manifest["raw_file_path"] == EXPECTED_RAW_RELATIVE
        assert str(tmp_path) not in result.manifest_path.read_text(encoding="utf-8")

    def test_absolute_root_outside_cwd_is_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        outside = tmp_path.parent / "outside-repo"
        outside.mkdir(exist_ok=True)
        store = LocalCaptureStore(raw_root=outside / "raw", manifest_root=outside / "manifests")

        with pytest.raises(StorageError, match="outside the working directory"):
            persist_browse(store, make_page(browse_fixture_bytes))
        assert not (outside / "raw" / EXPECTED_RAW_RELATIVE).exists()

    def test_non_rawpage_argument_rejected(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(TypeError):
            persist_browse(LocalCaptureStore(), object())  # type: ignore[arg-type]

    def test_empty_capture_id_rejected(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError):
            persist_browse(LocalCaptureStore(), make_page(browse_fixture_bytes), capture_id="")


class TestAtomicity:
    def test_manifest_write_failure_cleans_up_raw(self, monkeypatch, tmp_path, browse_fixture_bytes) -> None:
        monkeypatch.chdir(tmp_path)
        store = LocalCaptureStore()
        page = make_page(browse_fixture_bytes)

        real_replace = os.replace

        def failing_replace(src, dst, *args, **kwargs):
            if str(dst).endswith(".manifest.json"):
                raise OSError("simulated manifest replace failure")
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(OSError, match="simulated manifest replace failure"):
            persist_browse(store, page)

        assert not (tmp_path / EXPECTED_RAW_RELATIVE).exists()
        assert not (tmp_path / EXPECTED_MANIFEST_RELATIVE).exists()
