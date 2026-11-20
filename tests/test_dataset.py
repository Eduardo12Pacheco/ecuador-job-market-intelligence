"""Pruebas offline del conjunto de datos analítico canónico de desarrollo.

El conjunto de datos es una proyección versionada y determinista de una
proyección canónica existente (tuplas de ``CanonicalJob``) más los metadatos de
captura persistidos: todo campo canónico se conserva valor por valor (incluidos
todos los campos ``*_raw`` y ``snapshot_id``), y las únicas adiciones son
evidencias de habilidades derivadas y transparentes. Un registro sin
coincidencias es explícitamente ``no_evidence``.

El accesorio de exploración versionado (``data/sample/himalayas_browse_page_1.json``)
hace las veces de captura en vivo en estas pruebas; nunca se toca la red.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import (
    BROWSE_ENDPOINT,
    BROWSE_SAMPLE_JSON,
    default_job,
)

from job_market_intelligence.analysis.dataset import (
    DATASET_KIND,
    DATASET_VERSION,
    DatasetError,
    DatasetIntegrityError,
    build_development_dataset,
    resolve_snapshot_id,
    serialize_dataset,
)
from job_market_intelligence.analysis.matcher import MATCHER_VERSION
from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    load_taxonomy,
)
from job_market_intelligence.ingestion.parser import parse_job, parse_page

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH
DEVELOPMENT_DATASET_PATH = REPO_ROOT / "data" / "analytics" / "development-sample-0.1.0.json"

CAPTURED_AT_ISO = "2026-08-02T17:03:28.193510+00:00"
UPDATED_AT_UTC_ISO = "2026-08-02T05:48:40+00:00"

CANONICAL_FIELDS = {
    "canonical_id",
    "source",
    "source_id",
    "source_url",
    "application_url",
    "snapshot_id",
    "title_raw",
    "company_raw",
    "company_slug_raw",
    "excerpt_raw",
    "description_html_raw",
    "location_restrictions_raw",
    "location_scope",
    "timezone_restrictions_raw",
    "employment_type_raw",
    "seniority_raw",
    "categories_raw",
    "salary_min_raw",
    "salary_max_raw",
    "salary_period_raw",
    "currency_raw",
    "published_at_raw",
    "published_at_utc",
    "expires_at_raw",
    "expires_at_utc",
    "first_seen_at",
    "last_seen_at",
    "observation_status",
    "quality_flags",
}


def sample_manifest(**overrides) -> dict:
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
        "captured_at": CAPTURED_AT_ISO,
        "updated_at_raw": 1785649720,
        "updated_at_utc": UPDATED_AT_UTC_ISO,
        "timestamp_unit": "unix_seconds",
        "total_count": 94542,
        "returned_jobs": 20,
        "raw_file_path": "data/raw/x/00000000.json",
        "raw_sha256": "0" * 64,
        "adapter_version": "0.1.0",
        "attribution_url": "https://himalayas.app",
        "complete": False,
        "warnings": ["bounded_single_page_capture"],
        "errors": [],
    }
    manifest.update(overrides)
    return manifest


def parsed_capture_at() -> datetime:
    value = datetime.fromisoformat(CAPTURED_AT_ISO)
    assert value.tzinfo is not None
    return value


def parsed_jobs_from_fixture() -> tuple:
    """Analiza el accesorio de exploración versionado de 20 registros en empleos canónicos."""
    payload = json.loads(BROWSE_SAMPLE_JSON.read_text(encoding="utf-8"))
    parsed = parse_page(payload)
    captured_at = parsed_capture_at()
    return tuple(
        parse_job(
            raw,
            snapshot_id="cap_fixture",
            captured_at=captured_at,
            expected_unit=parsed.timestamp_unit,
        )
        for raw in parsed.raw_jobs
    )


def one_job(**overrides) -> tuple:
    raw = default_job(0, 0, **overrides)
    return (parse_job(raw, snapshot_id="snap-fixed", captured_at=parsed_capture_at()),)


class TestCanonicalFieldPreservation:
    def test_every_canonical_field_preserved(self) -> None:
        job = one_job(
            title="Python Engineer",
            description="<p>Python expert</p>",
            excerpt="We need python skills",
        )[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)
        record = dataset["records"][0]
        assert set(record) == CANONICAL_FIELDS | {"skill_evidence"}
        assert record["canonical_id"] == job.canonical_id
        assert record["source"] == job.source
        assert record["source_id"] == job.source_id
        assert record["title_raw"] == job.title_raw == "Python Engineer"
        assert record["company_raw"] == job.company_raw
        assert record["excerpt_raw"] == job.excerpt_raw
        assert record["description_html_raw"] == job.description_html_raw == "<p>Python expert</p>"
        assert record["location_scope"] == job.location_scope.value
        assert record["observation_status"] == job.observation_status.value
        assert record["quality_flags"] == job.quality_flags
        assert record["first_seen_at"] == CAPTURED_AT_ISO

    def test_fixture_raw_fields_value_for_value(self) -> None:
        jobs = parsed_jobs_from_fixture()
        payload = json.loads(BROWSE_SAMPLE_JSON.read_text(encoding="utf-8"))
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        assert len(dataset["records"]) == 20
        for record, raw in zip(dataset["records"], payload["jobs"], strict=True):
            assert record["title_raw"] == raw["title"]
            assert record["company_raw"] == raw["companyName"]
            assert record["description_html_raw"] == raw["description"]
            assert record["excerpt_raw"] == raw.get("excerpt")
            assert record["categories_raw"] == raw.get("categories")
            assert record["location_restrictions_raw"] == raw.get("locationRestrictions")
            assert record["source_id"] == raw["guid"]

    def test_snapshot_id_preserved_through_projection(self) -> None:
        job = one_job()[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)
        assert dataset["records"][0]["snapshot_id"] == "snap-fixed"


class TestSnapshotIdentity:
    def test_snapshot_id_from_manifest_capture_id(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        assert dataset["capture_identity"]["snapshot_id"] == "cap_fixture"
        assert dataset["capture_identity"]["snapshot_id_origin"] == "manifest_capture_id"
        assert all(r["snapshot_id"] == "cap_fixture" for r in dataset["records"])

    def test_explicit_snapshot_id_wins(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(
            jobs, manifest=sample_manifest(), taxonomy=taxonomy, snapshot_id="explicit-run-1"
        )
        assert dataset["capture_identity"]["snapshot_id"] == "explicit-run-1"
        assert dataset["capture_identity"]["snapshot_id_origin"] == "explicit"

    def test_manifest_without_capture_id_fails_closed(self) -> None:
        manifest = sample_manifest()
        del manifest["capture_id"]
        jobs = one_job()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        with pytest.raises(DatasetError, match="snapshot_id"):
            build_development_dataset(jobs, manifest=manifest, taxonomy=taxonomy)

    def test_resolve_snapshot_id_helper(self) -> None:
        assert resolve_snapshot_id(sample_manifest()) == ("cap_fixture", "manifest_capture_id")
        assert resolve_snapshot_id(sample_manifest(), "x") == ("x", "explicit")


class TestSampleMetadata:
    def test_development_sample_metadata(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        assert dataset["dataset_kind"] == "development_sample"
        assert dataset["dataset_version"] == "0.1.0"
        assert dataset["taxonomy_version"] == taxonomy.version == "technical-skills-0.1.0"
        assert dataset["matcher_version"] == MATCHER_VERSION
        sample = dataset["sample"]
        assert sample["page"] == 1
        assert sample["offset"] == 0
        assert sample["limit"] == 20
        assert sample["records"] == 20
        assert sample["total_count"] == 94542
        assert sample["complete"] is False
        assert sample["warnings"] == ["bounded_single_page_capture"]
        assert any("not market coverage" in note for note in sample["limitations"])

    def test_complete_true_manifest_fails_closed(self) -> None:
        # La ruta de muestra de desarrollo nunca debe producir una muestra completa: se
        # rechaza un manifiesto que declare complete: true en lugar de heredarlo.
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        with pytest.raises(DatasetError, match="complete"):
            build_development_dataset(jobs, manifest=sample_manifest(complete=True), taxonomy=taxonomy)

    def test_capture_identity_from_manifest(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        identity = dataset["capture_identity"]
        assert identity["source"] == "himalayas"
        assert identity["endpoint"] == BROWSE_ENDPOINT
        assert identity["captured_at"] == CAPTURED_AT_ISO
        assert identity["api_updated_at_utc"] == UPDATED_AT_UTC_ISO
        assert identity["api_updated_at_raw"] == 1785649720
        assert identity["raw_sha256"] == "0" * 64
        assert identity["adapter_version"] == "0.1.0"
        assert identity["attribution_url"] == "https://himalayas.app"
        assert identity["raw_file_path"] == "data/raw/x/00000000.json"

    def test_manifest_path_recorded_when_given(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(
            jobs, manifest=sample_manifest(), taxonomy=taxonomy, manifest_path="data/manifests/x/00000000.manifest.json"
        )
        assert dataset["capture_identity"]["manifest_path"] == "data/manifests/x/00000000.manifest.json"


class TestSkillEvidence:
    def test_no_match_record_is_explicit_no_evidence(self) -> None:
        job = one_job(title="Bilingual Writer", description="<p>Editing and proofreading</p>")[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)
        evidence = dataset["records"][0]["skill_evidence"]
        assert evidence["evidence_status"] == "no_evidence"
        assert evidence["skills"] == []
        assert evidence["taxonomy_version"] == "technical-skills-0.1.0"

    def test_matched_record_evidence_structure(self) -> None:
        job = one_job(title="ML Engineer", description="<p>Python and PyTorch</p>")[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)
        evidence = dataset["records"][0]["skill_evidence"]
        assert evidence["evidence_status"] == "matched"
        assert "skill.python" in evidence["skills"]
        assert "skill.pytorch" in evidence["skills"]
        for entry in evidence["evidence"]:
            assert {
                "skill_id",
                "field",
                "matched_term",
                "term_type",
                "excerpt",
                "occurrence_count",
            } <= set(entry)
            assert entry["field"] in {"title_raw", "excerpt_raw", "categories_raw", "description_html_raw"}
            assert entry["term_type"] in {"keyword", "alias"}
        assert evidence["skipped_fields"] == []

    def test_missing_fields_skipped_and_reported(self) -> None:
        job = one_job(excerpt=None, description="<p>Python</p>")[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)
        evidence = dataset["records"][0]["skill_evidence"]
        assert "excerpt_raw" in evidence["skipped_fields"]
        assert "excerpt_raw" not in evidence["searched_fields"]

    def test_raw_description_unchanged_while_matching_used_visible_text(self) -> None:
        job = one_job(description="<p>We need <strong>Python</strong> skills</p>")[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)
        record = dataset["records"][0]
        assert record["description_html_raw"] == "<p>We need <strong>Python</strong> skills</p>"
        assert record["skill_evidence"]["evidence_status"] == "matched"


class TestDeterminismAndVersioning:
    def test_serialization_is_deterministic(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        first = serialize_dataset(dataset)
        second = serialize_dataset(dataset)
        assert first == second
        assert first.endswith(b"\n")
        assert json.loads(first) == dataset

    def test_no_wall_clock_fields(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        assert "generated_at" not in dataset
        assert "capture_time" not in dataset and "build_time" not in dataset
        assert all("generated_at" not in record for record in dataset["records"])

    def test_taxonomy_version_in_dataset_and_report(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        assert dataset["taxonomy_version"] == "technical-skills-0.1.0"
        assert dataset["quality_report"]["skill_coverage"]["taxonomy_version"] == "technical-skills-0.1.0"

    def test_quality_report_embedded_matches_records(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        assert dataset["quality_report"]["record_count"] == len(dataset["records"]) == 20

    def test_mismatched_capture_clock_fails_closed(self) -> None:
        job = parse_job(
            default_job(0, 0),
            snapshot_id="snap-fixed",
            captured_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC),  # ≠ captured_at del manifiesto
        )
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        with pytest.raises(DatasetIntegrityError, match="captured_at"):
            build_development_dataset((job,), manifest=sample_manifest(returned_jobs=1), taxonomy=taxonomy)

    def test_naive_manifest_captured_at_rejected(self) -> None:
        job = one_job()[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        manifest = sample_manifest(returned_jobs=1, captured_at="2026-08-02T17:03:28.193510")
        with pytest.raises(DatasetIntegrityError, match="timezone"):
            build_development_dataset((job,), manifest=manifest, taxonomy=taxonomy)

    def test_missing_required_manifest_key_rejected(self) -> None:
        job = one_job()[0]
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        manifest = sample_manifest(returned_jobs=1)
        del manifest["total_count"]
        with pytest.raises(DatasetError, match="total_count"):
            build_development_dataset((job,), manifest=manifest, taxonomy=taxonomy)


class TestCommittedDevelopmentSample:
    def test_location_scope_distribution(self) -> None:
        dataset = json.loads(DEVELOPMENT_DATASET_PATH.read_text(encoding="utf-8"))
        counts = Counter(record["location_scope"] for record in dataset["records"])
        assert counts["worldwide"] == 12
        assert counts["other_country"] == 8
        assert counts["explicit_ec"] == 0
        assert sum(counts.values()) == len(dataset["records"]) == 20


class TestConstants:
    def test_dataset_version_and_kind(self) -> None:
        assert DATASET_VERSION == "0.1.0"
        assert DATASET_KIND == "development_sample"

    def test_timezone_safe_iso_output(self) -> None:
        jobs = parsed_jobs_from_fixture()
        taxonomy = load_taxonomy(ARTIFACT_PATH)
        dataset = build_development_dataset(jobs, manifest=sample_manifest(), taxonomy=taxonomy)
        for record in dataset["records"]:
            for key in ("first_seen_at", "last_seen_at"):
                value = datetime.fromisoformat(record[key])
                assert value.tzinfo is not None
                assert value.utcoffset() == UTC.utcoffset(None)
