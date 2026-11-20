"""Pruebas offline del informe de calidad determinista.

El informe se deriva por completo de las entradas del conjunto de datos de
desarrollo más el manifiesto persistido: no se consulta el reloj de pared, por
lo que el informe es reproducible. La frescura es un cálculo explícito y
seguro ante zonas horarias
``age_at_capture_seconds = captured_at - api_updated_at_utc`` que usa solo las
marcas de tiempo ya almacenadas en el manifiesto.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from conftest import default_job
from test_dataset import CAPTURED_AT_ISO, UPDATED_AT_UTC_ISO, parsed_capture_at, sample_manifest

from job_market_intelligence.analysis.matcher import SEARCHED_FIELDS, match_job
from job_market_intelligence.analysis.quality import build_quality_report
from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    SkillDefinition,
    Taxonomy,
)
from job_market_intelligence.ingestion.parser import parse_job

ARTIFACT_PATH = Path(__file__).resolve().parents[1] / TAXONOMY_ARTIFACT_DEFAULT_PATH


def parsed_job(**overrides):
    return parse_job(
        default_job(0, 0, **overrides),
        snapshot_id="cap_fixture",
        captured_at=parsed_capture_at(),
    )


def small_taxonomy() -> Taxonomy:
    return Taxonomy(
        version="test-taxonomy-0.1.0",
        skills=(
            SkillDefinition("skill.python", "Python", "programming_language", ("python",)),
            SkillDefinition("skill.java", "Java", "programming_language", ("java",)),
        ),
        rules=(("boundary_matching", "aliases never match inside larger words"),),
    )


def report_for(jobs, manifest=None) -> dict:
    """Construye el informe con los resultados de coincidencia derivados de la misma taxonomía."""
    taxonomy = small_taxonomy()
    if manifest is None:
        manifest = sample_manifest(returned_jobs=len(jobs))
    results = [match_job(job, taxonomy) for job in jobs]
    return build_quality_report(jobs, results, manifest=manifest, taxonomy=taxonomy)


class TestCounts:
    def test_record_count(self) -> None:
        jobs = [parsed_job(), parsed_job(guid="https://himalayas.app/jobs/2")]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=2))
        assert report["record_count"] == 2

    def test_missing_field_counts_explicit_field_set(self) -> None:
        jobs = [
            parsed_job(excerpt=None, categories=[], title=""),
        ]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=1))
        assert report["checked_fields"] == list(SEARCHED_FIELDS)
        assert report["missing_field_counts"] == {
            "title_raw": 1,
            "excerpt_raw": 1,
            "categories_raw": 1,
            "description_html_raw": 0,
        }

    def test_observation_status_counts(self) -> None:
        jobs = [parsed_job(), parsed_job(guid="https://himalayas.app/jobs/2")]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=2))
        assert report["observation_status_counts"]["active"] == 2

    def test_duplicate_source_id_counts(self) -> None:
        jobs = [
            parsed_job(),
            parsed_job(),  # guid duplicado
            parsed_job(guid="https://himalayas.app/jobs/3"),
        ]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=3))
        assert report["duplicate_counts"]["duplicate_source_id_records"] == 1
        assert report["duplicate_counts"]["duplicate_source_ids"] == [jobs[0].source_id]

    def test_empty_source_id_records_not_counted_as_duplicates(self) -> None:
        jobs = [parsed_job(guid=""), parsed_job(guid="")]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=2))
        assert report["duplicate_counts"]["duplicate_source_id_records"] == 0
        assert report["duplicate_counts"]["duplicate_source_ids"] == []
        assert report["observation_status_counts"]["invalid"] == 2


class TestSkillCoverage:
    def test_per_skill_counts_include_zero_entries(self) -> None:
        jobs = [parsed_job(description="<p>Python expert</p>")]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=1))
        assert report["skill_coverage"]["skill_counts"] == {"skill.python": 1, "skill.java": 0}
        assert report["skill_coverage"]["taxonomy_version"] == "test-taxonomy-0.1.0"

    def test_records_with_and_without_evidence(self) -> None:
        jobs = [
            parsed_job(description="<p>Python expert</p>"),
            parsed_job(guid="https://himalayas.app/jobs/2", description="<p>Editing and proofreading</p>"),
        ]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=2))
        coverage = report["skill_coverage"]
        assert coverage["records_with_evidence"] == 1
        assert coverage["records_without_evidence"] == 1
        assert len(coverage["records_no_evidence"]) == 1

    def test_per_skill_counts_sorted_deterministically(self) -> None:
        jobs = [parsed_job(description="<p>Python and Java</p>")]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=1))
        assert list(report["skill_coverage"]["skill_counts"]) == [
            "skill.java",
            "skill.python",
        ]  # empates → orden por id


class TestFreshness:
    def test_age_calculation_explicit_and_timezone_safe(self) -> None:
        captured = datetime.fromisoformat(CAPTURED_AT_ISO)
        updated = datetime.fromisoformat(UPDATED_AT_UTC_ISO)
        expected = (captured - updated).total_seconds()
        jobs = [parsed_job()]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=1))
        freshness = report["freshness"]
        assert freshness["source_updated_at_utc"] == UPDATED_AT_UTC_ISO
        assert freshness["captured_at"] == CAPTURED_AT_ISO
        assert freshness["age_at_capture_seconds"] == expected
        assert "captured_at - api_updated_at_utc" in freshness["formula"]

    def test_null_updated_at_handled_explicitly(self) -> None:
        manifest = sample_manifest(returned_jobs=1, updated_at_utc=None)
        jobs = [parsed_job()]
        report = report_for(jobs, manifest=manifest)
        assert report["freshness"]["age_at_capture_seconds"] is None
        assert report["freshness"]["source_updated_at_utc"] is None

    def test_freshness_timezone_safe_with_offset_manifest(self) -> None:
        # Una marca de tiempo del manifiesto con offset explícito no-UTC debe producir la
        # misma edad basada en UTC que la cadena UTC equivalente.
        captured = datetime.fromisoformat(CAPTURED_AT_ISO)
        updated = datetime.fromisoformat(UPDATED_AT_UTC_ISO)
        expected = (captured - updated).total_seconds()
        jobs = [parsed_job()]
        offset_manifest = sample_manifest(
            returned_jobs=1,
            captured_at="2026-08-02T19:03:28.193510+02:00",  # mismo instante que CAPTURED_AT_ISO
        )
        report = report_for(jobs, manifest=offset_manifest)
        assert report["freshness"]["age_at_capture_seconds"] == expected


class TestLimitations:
    def test_limitations_note_explicit(self) -> None:
        jobs = [parsed_job()]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=1))
        note = report["limitations_note"]
        assert "20 records" in note
        assert "one page" in note
        assert "not market coverage" in note
        assert "complete" in note

    def test_taxonomy_version_preserved_in_report(self) -> None:
        jobs = [parsed_job()]
        report = report_for(jobs, manifest=sample_manifest(returned_jobs=1))
        assert report["skill_coverage"]["taxonomy_version"] == "test-taxonomy-0.1.0"
