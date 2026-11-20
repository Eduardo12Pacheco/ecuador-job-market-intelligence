"""Pruebas offline del comando de materialización.

``materialize_development_dataset`` lee un par existente de página cruda
persistida + manifiesto (o un accesorio que haga sus veces), verifica la
integridad, analiza la proyección canónica y escribe el conjunto de datos de
desarrollo versionado. Todo se ejecuta contra archivos locales bajo ``tmp_path``
con los bytes del accesorio de exploración versionado; nunca se toca la red.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import BROWSE_ENDPOINT, BROWSE_SAMPLE_JSON

from job_market_intelligence.analysis.dataset import DatasetError, DatasetIntegrityError
from job_market_intelligence.analysis.materialize import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_TAXONOMY_PATH,
    materialize_development_dataset,
)
from job_market_intelligence.analysis.taxonomy import TAXONOMY_ARTIFACT_DEFAULT_PATH

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_MANIFEST = REPO_ROOT / DEFAULT_MANIFEST_PATH
LIVE_RAW_SHA256 = "0370798f7af4b0e39ab92fd0d486577f58cdd415812e612d6b86657ac07ab101"


def fixture_bytes() -> bytes:
    return BROWSE_SAMPLE_JSON.read_bytes()


def write_capture_pair(tmp_path: Path) -> dict:
    """Escribe una página cruda + manifiesto bajo tmp_path usando los bytes del accesorio de exploración."""
    raw_relative = "data/raw/fixture/jobs_api_00000000/00000000.json"
    raw_path = tmp_path / raw_relative
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(fixture_bytes())
    manifest = {
        "manifest_version": 1,
        "capture_id": "cap_fixture",
        "source": "himalayas",
        "endpoint": BROWSE_ENDPOINT,
        "request_params": {"limit": 20, "offset": 0},
        "offset": 0,
        "limit": 20,
        "http_status": 200,
        "content_type": "application/json",
        "captured_at": "2026-08-02T17:38:06.487596+00:00",
        "updated_at_raw": 1785649720,
        "updated_at_utc": "2026-08-02T05:48:40+00:00",
        "timestamp_unit": "unix_seconds",
        "total_count": 94542,
        "returned_jobs": 20,
        "raw_file_path": raw_relative,
        "raw_sha256": hashlib.sha256(fixture_bytes()).hexdigest(),
        "adapter_version": "0.1.0",
        "attribution_url": "https://himalayas.app",
        "complete": False,
        "warnings": ["bounded_single_page_capture"],
        "errors": [],
    }
    manifest_path = tmp_path / "data/manifests/fixture/jobs_api_00000000/00000000.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return {"manifest": manifest, "manifest_path": manifest_path}


class TestMaterialization:
    def test_materialize_from_persisted_capture_offline(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        output = tmp_path / "out" / "dataset.json"
        taxonomy_path = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH

        written = materialize_development_dataset(
            manifest_path=pair["manifest_path"],
            taxonomy_path=taxonomy_path,
            output_path=output,
        )

        assert written == output
        dataset = json.loads(output.read_text(encoding="utf-8"))
        assert dataset["dataset_kind"] == "development_sample"
        assert dataset["sample"]["records"] == 20
        assert dataset["sample"]["complete"] is False
        assert dataset["quality_report"]["record_count"] == 20
        assert dataset["capture_identity"]["snapshot_id"] == "cap_fixture"
        assert dataset["capture_identity"]["raw_sha256"] == hashlib.sha256(fixture_bytes()).hexdigest()

    def test_materialize_is_reproducible_byte_for_byte(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        taxonomy_path = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH
        first = materialize_development_dataset(
            manifest_path=pair["manifest_path"],
            taxonomy_path=taxonomy_path,
            output_path=tmp_path / "out" / "dataset.json",
        )
        second = materialize_development_dataset(
            manifest_path=pair["manifest_path"],
            taxonomy_path=taxonomy_path,
            output_path=tmp_path / "out" / "dataset.json",
        )
        assert first.read_bytes() == second.read_bytes()

    def test_sha_mismatch_fails_closed(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        raw_path = tmp_path / pair["manifest"]["raw_file_path"]
        raw_path.write_bytes(b"corrupted bytes")
        with pytest.raises(DatasetIntegrityError, match="SHA-256"):
            materialize_development_dataset(
                manifest_path=pair["manifest_path"],
                taxonomy_path=REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH,
                output_path=tmp_path / "out" / "dataset.json",
            )
        assert not (tmp_path / "out" / "dataset.json").exists()

    def test_manifest_payload_mismatch_fails_closed(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        manifest = json.loads(pair["manifest_path"].read_text(encoding="utf-8"))
        manifest["offset"] = 20
        pair["manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(DatasetIntegrityError, match="offset"):
            materialize_development_dataset(
                manifest_path=pair["manifest_path"],
                taxonomy_path=REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH,
                output_path=tmp_path / "out" / "dataset.json",
            )
        assert not (tmp_path / "out" / "dataset.json").exists()

    def test_complete_true_manifest_rejected(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        manifest = json.loads(pair["manifest_path"].read_text(encoding="utf-8"))
        manifest["complete"] = True
        pair["manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(DatasetError, match="complete"):
            materialize_development_dataset(
                manifest_path=pair["manifest_path"],
                taxonomy_path=REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH,
                output_path=tmp_path / "out" / "dataset.json",
            )
        assert not (tmp_path / "out" / "dataset.json").exists()

    def test_missing_raw_file_fails_closed(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        (tmp_path / pair["manifest"]["raw_file_path"]).unlink()
        with pytest.raises(DatasetIntegrityError, match="raw"):
            materialize_development_dataset(
                manifest_path=pair["manifest_path"],
                taxonomy_path=REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH,
                output_path=tmp_path / "out" / "dataset.json",
            )

    def test_different_existing_output_refused(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        pair = write_capture_pair(tmp_path)
        output = tmp_path / "out" / "dataset.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"stale bytes")
        with pytest.raises(DatasetError, match="contenido diferente"):
            materialize_development_dataset(
                manifest_path=pair["manifest_path"],
                taxonomy_path=REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH,
                output_path=output,
            )
        assert output.read_bytes() == b"stale bytes"


class TestDefaults:
    def test_default_paths_are_documented(self) -> None:
        assert DEFAULT_MANIFEST_PATH == "data/manifests/himalayas/jobs_api_6b8244a52a80/00000000.manifest.json"
        assert DEFAULT_TAXONOMY_PATH == TAXONOMY_ARTIFACT_DEFAULT_PATH
        assert DEFAULT_OUTPUT_PATH == "data/analytics/development-sample-0.1.0.json"

    def test_committed_live_manifest_matches_documented_capture(self) -> None:
        # Verificación de solo lectura del manifiesto versionado: la identidad de
        # captura en vivo documentada (20 registros, totalCount=94520, SHA-256
        # crudo) es de donde se genera el artefacto de desarrollo versionado.
        assert LIVE_MANIFEST.exists()
        manifest = json.loads(LIVE_MANIFEST.read_text(encoding="utf-8"))
        assert manifest["returned_jobs"] == 20
        assert manifest["total_count"] == 94520
        assert manifest["raw_sha256"] == LIVE_RAW_SHA256
        assert manifest["complete"] is False
        assert manifest["raw_file_path"] == DEFAULT_MANIFEST_PATH.replace("manifests/", "raw/").replace(
            ".manifest.json", ".json"
        )
