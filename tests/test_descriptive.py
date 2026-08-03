"""Pruebas offline del análisis descriptivo de la muestra de desarrollo.

El análisis descriptivo consume SOLO el conjunto de datos analítico confirmado
(``data/analytics/development-sample-0.1.0.json``) y el artefacto de taxonomía
versionado (``data/taxonomy/technical-skills-0.1.0.json``, usado únicamente
como referencia de esquema ID -> nombre/categoría canónicos). No intervienen
páginas crudas, manifiestos, respuestas de API ni red, y no se consulta el
reloj de pared.

Contratos bajo prueba:

- la frecuencia de habilidades cuenta registros distintos (una habilidad
  cuenta como máximo una vez por registro aunque sus términos aparezcan
  repetidos);
- la cobertura por categoría cuenta registros distintos por categoría (como
  máximo una vez por registro y por categoría) con la definición incluida;
- las habilidades de la taxonomía sin coincidencias se listan y se distinguen
  explícitamente de los registros ``no_evidence``;
- los pares de coocurrencia no están ordenados y son canónicos
  ``(skill_a, skill_b)`` con ``skill_a < skill_b``, nunca reflexivos, nunca
  invertidos, y se cuentan una vez por registro;
- la matriz de coocurrencia usa ids de habilidad ordenados, conteos enteros,
  una diagonal cero y es simétrica;
- se propagan el id de instantánea, la versión de taxonomía, el tipo
  ``development_sample``, 20 registros, una página y ``complete: false``;
- se rechazan los conjuntos de datos que no son la muestra de desarrollo
  documentada de 20 registros (tipo incorrecto, forma de muestra incorrecta,
  instantánea distinta, complete: true, versión de taxonomía no coincidente);
- los metadatos de calidad/frescura se propagan sin cambiar su significado;
- las salvaguardas dicen explícitamente que la salida es solo evidencia
  descriptiva por palabras clave y NO correlación, causalidad, cobertura de
  mercado ni representatividad;
- la salida es determinista byte por byte.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from job_market_intelligence.analysis.descriptive import (
    ANALYSIS_KIND,
    ANALYSIS_VERSION,
    SAMPLE_LIMIT,
    SAMPLE_OFFSET,
    SAMPLE_PAGE,
    SAMPLE_RECORDS,
    SNAPSHOT_ID,
    build_descriptive_analysis,
    category_coverage,
    cooccurrence_matrix,
    cooccurrence_pairs,
    quality_freshness_summary,
    serialize_analysis,
    skill_frequency,
    validate_development_sample,
    zero_match_skills,
)
from job_market_intelligence.analysis.errors import DescriptiveError
from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    load_taxonomy,
    taxonomy_from_dict,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "data" / "analytics" / "development-sample-0.1.0.json"
TAXONOMY_PATH = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH


@pytest.fixture(scope="session")
def dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def taxonomy():
    return load_taxonomy(TAXONOMY_PATH)


@pytest.fixture(scope="session")
def analysis(dataset, taxonomy) -> dict:
    return build_descriptive_analysis(dataset, taxonomy)


class TestSkillFrequency:
    def test_known_frequencies(self, analysis) -> None:
        freq = analysis["skill_frequency"]
        assert freq["skill.ai"] == 19
        assert freq["skill.machine_learning"] == 3
        assert freq["skill.python"] == 2
        assert freq["skill.data_science"] == 2
        assert freq["skill.aws"] == 2

    def test_frequency_matches_embedded_quality_report(self, analysis, dataset) -> None:
        # Ambos son conteos de registros distintos sobre la misma entrada; deben coincidir.
        # El informe de calidad también incluye conteos cero explícitos para las habilidades
        # sin coincidencias de la taxonomía, mientras que skill_frequency solo lista las que coinciden.
        embedded = dataset["quality_report"]["skill_coverage"]["skill_counts"]
        assert analysis["skill_frequency"] == {
            skill_id: count for skill_id, count in embedded.items() if count > 0
        }

    def test_deterministic_ordering(self, analysis) -> None:
        items = list(analysis["skill_frequency"].items())
        assert items == sorted(items, key=lambda kv: (-kv[1], kv[0]))
        assert items[0] == ("skill.ai", 19)


class TestCategoryCoverage:
    def test_known_coverage(self, analysis) -> None:
        categories = {c["category"]: c for c in analysis["category_coverage"]["categories"]}
        assert categories["ml_ai"]["records"] == 19
        assert categories["programming_language"]["records"] == 4
        assert categories["cloud_platform"]["records"] == 2
        assert categories["framework_library"]["records"] == 1
        assert categories["data_platform"]["records"] == 1
        assert categories["developer_tool"]["records"] == 1
        assert categories["mobile"]["records"] == 1
        assert categories["security_identity"]["records"] == 1

    def test_definition_says_distinct_records(self, analysis) -> None:
        definition = analysis["category_coverage"]["definition"].lower()
        assert "distinct records" in definition
        assert "at most once" in definition

    def test_matched_skill_totals(self, analysis, taxonomy) -> None:
        categories = {c["category"]: c for c in analysis["category_coverage"]["categories"]}
        assert categories["ml_ai"]["matched_skill_count"] == 7
        assert categories["programming_language"]["matched_skill_count"] == 4
        assert categories["developer_tool"]["matched_skill_count"] == 9
        assert categories["developer_tool"]["total_taxonomy_skills"] == 10
        # Todas las categorías de la taxonomía están presentes en la tabla de cobertura.
        assert set(categories) == {s.category for s in taxonomy.skills}


class TestZeroMatchSkills:
    def test_zero_match_skills_present(self, analysis) -> None:
        zero = analysis["zero_match_skills"]["skills"]
        ids = [s["skill_id"] for s in zero]
        assert ids == ["skill.cpp", "skill.csharp", "skill.git", "skill.java"]
        assert all(s["matched_records"] == 0 for s in zero)
        assert analysis["zero_match_skills"]["count"] == 4

    def test_matched_skills_are_not_zero_match(self, analysis) -> None:
        zero_ids = {s["skill_id"] for s in analysis["zero_match_skills"]["skills"]}
        assert zero_ids.isdisjoint(analysis["skill_frequency"])

    def test_zero_match_distinct_from_no_evidence(self, analysis, dataset) -> None:
        definition = analysis["zero_match_skills"]["definition"].lower()
        assert "not evidence" in definition
        assert "no_evidence" in definition
        # La muestra tiene 0 registros no_evidence y 4 habilidades sin coincidencias; el
        # artefacto mantiene ambos hechos explícitos.
        report = dataset["quality_report"]["skill_coverage"]
        assert report["records_without_evidence"] == 0
        assert analysis["quality_freshness_summary"]["records_without_evidence"] == 0
        assert analysis["zero_match_skills"]["count"] == 4


class TestCooccurrence:
    def test_no_reflexive_pairs_no_reversed_duplicates(self, analysis) -> None:
        seen: set[tuple[str, str]] = set()
        for pair in analysis["cooccurrence_pairs"]["pairs"]:
            a, b = pair["skill_a"], pair["skill_b"]
            assert a != b
            assert a < b
            assert (a, b) not in seen
            seen.add((a, b))

    def test_known_pair_counts(self, analysis) -> None:
        pairs = {
            (p["skill_a"], p["skill_b"]): p["records"]
            for p in analysis["cooccurrence_pairs"]["pairs"]
        }
        assert pairs[("skill.ai", "skill.machine_learning")] == 3
        assert pairs[("skill.ai", "skill.python")] == 2
        assert pairs[("skill.machine_learning", "skill.python")] == 2
        assert pairs[("skill.ai", "skill.data_science")] == 2
        assert pairs[("skill.ai", "skill.aws")] == 2
        assert pairs[("skill.ios", "skill.swift")] == 1

    def test_deterministic_pair_ordering(self, analysis) -> None:
        pairs = analysis["cooccurrence_pairs"]["pairs"]
        assert pairs == sorted(
            pairs, key=lambda p: (-p["records"], p["skill_a"], p["skill_b"])
        )
        assert pairs[0] == {"skill_a": "skill.ai", "skill_b": "skill.machine_learning", "records": 3}

    def test_definition_documented(self, analysis) -> None:
        definition = analysis["cooccurrence_pairs"]["definition"].lower()
        assert "unordered" in definition
        assert "once per record" in definition
        assert "never" in definition

    def test_matrix_sorted_symmetric_zero_diagonal(self, analysis) -> None:
        matrix_doc = analysis["cooccurrence_matrix"]
        skill_ids = matrix_doc["skill_ids"]
        matrix = matrix_doc["matrix"]
        assert skill_ids == sorted(skill_ids)
        assert len(skill_ids) == len(matrix) == 37
        for i in range(len(skill_ids)):
            assert len(matrix[i]) == 37
            assert matrix[i][i] == 0
            for j in range(len(skill_ids)):
                assert matrix[i][j] == matrix[j][i]
        i_ai = skill_ids.index("skill.ai")
        i_ml = skill_ids.index("skill.machine_learning")
        assert matrix[i_ai][i_ml] == 3
        # La suma de la fila de skill.ai equivale a las ocurrencias totales de pares que involucran a ai.
        assert sum(matrix[i_ai]) == sum(p["records"] for p in analysis["cooccurrence_pairs"]["pairs"] if "skill.ai" in (p["skill_a"], p["skill_b"]))

    def test_matrix_matches_pairs(self, analysis) -> None:
        matrix_doc = analysis["cooccurrence_matrix"]
        skill_ids = matrix_doc["skill_ids"]
        matrix = matrix_doc["matrix"]
        for pair in analysis["cooccurrence_pairs"]["pairs"]:
            assert matrix[skill_ids.index(pair["skill_a"])][skill_ids.index(pair["skill_b"])] == pair["records"]

    def test_definition_documents_diagonal(self, analysis) -> None:
        assert "zero" in analysis["cooccurrence_matrix"]["diagonal"].lower()


class TestPerRecordDeduplication:
    """Los ids de habilidad duplicados / la evidencia repetida en un registro no deben inflar los conteos."""

    def _records_with_duplicates(self) -> list[dict]:
        return [
            {"skill_evidence": {"skills": ["skill.ai", "skill.ai", "skill.ai"]}},
            {
                "skill_evidence": {
                    "skills": ["skill.ai", "skill.python", "skill.python"],
                    "evidence": [
                        {"skill_id": "skill.ai", "field": "title_raw", "matched_term": "ai"},
                        {"skill_id": "skill.ai", "field": "description_html_raw", "matched_term": "ai"},
                    ],
                }
            },
            {"skill_evidence": {"skills": []}},
        ]

    def test_frequency_not_inflated(self) -> None:
        freq = skill_frequency(self._records_with_duplicates())
        assert freq == {"skill.ai": 2, "skill.python": 1}

    def test_pairs_not_inflated(self) -> None:
        pairs = cooccurrence_pairs(self._records_with_duplicates())["pairs"]
        assert pairs == [{"skill_a": "skill.ai", "skill_b": "skill.python", "records": 1}]

    def test_single_skill_record_contributes_no_pair(self) -> None:
        records = [
            {"skill_evidence": {"skills": ["skill.ai"]}},
            {"skill_evidence": {"skills": ["skill.python"]}},
        ]
        assert cooccurrence_pairs(records)["pairs"] == []

    def test_category_counted_once_per_record(self, taxonomy) -> None:
        # Un registro con dos habilidades de la misma categoría cuenta una vez para ella.
        records = [
            {"skill_evidence": {"skills": ["skill.python", "skill.javascript"]}},
            {"skill_evidence": {"skills": ["skill.python"]}},
        ]
        categories = {c["category"]: c for c in category_coverage(records, taxonomy)["categories"]}
        assert categories["programming_language"]["records"] == 2

    def test_matrix_not_inflated(self, taxonomy) -> None:
        matrix_doc = cooccurrence_matrix(self._records_with_duplicates(), taxonomy)
        ids = matrix_doc["skill_ids"]
        assert matrix_doc["matrix"][ids.index("skill.ai")][ids.index("skill.python")] == 1


class TestMetadataPropagation:
    def test_identity_propagated(self, analysis) -> None:
        assert analysis["snapshot_id"] == SNAPSHOT_ID == "cap_0370798f7af4b0e3"
        assert analysis["taxonomy_version"] == "technical-skills-0.1.0"
        assert analysis["dataset_kind"] == "development_sample"
        assert analysis["source"] == "himalayas"
        assert analysis["attribution_url"] == "https://himalayas.app"
        assert analysis["analysis_kind"] == ANALYSIS_KIND
        assert analysis["analysis_version"] == ANALYSIS_VERSION

    def test_sample_shape_propagated(self, analysis) -> None:
        sample = analysis["sample"]
        assert sample["records"] == SAMPLE_RECORDS == 20
        assert sample["page"] == SAMPLE_PAGE == 1
        assert sample["limit"] == SAMPLE_LIMIT == 20
        assert sample["offset"] == SAMPLE_OFFSET == 0
        assert sample["complete"] is False

    def test_warning_mentions_bounded_sample(self, analysis) -> None:
        warning = analysis["sample"]["warning"]
        assert "20 records" in warning
        assert "one" in warning and "page" in warning
        assert "complete: false" in warning
        assert SNAPSHOT_ID in warning

    def test_quality_freshness_propagated(self, analysis, dataset) -> None:
        # Copiado sin cambiar su significado.
        assert analysis["quality_report"] == dataset["quality_report"]
        summary = analysis["quality_freshness_summary"]
        assert summary["record_count"] == 20
        assert summary["missing_field_counts"] == {
            "title_raw": 0,
            "excerpt_raw": 0,
            "categories_raw": 0,
            "description_html_raw": 0,
        }
        assert summary["duplicate_source_id_records"] == 0
        assert summary["records_with_evidence"] == 20
        assert summary["records_without_evidence"] == 0
        assert summary["age_at_capture_seconds"] == 45815.6095
        assert "age_at_capture_seconds = captured_at - api_updated_at_utc" in summary["freshness_formula"]

    def test_quality_summary_derived_not_invented(self, analysis) -> None:
        summary = analysis["quality_freshness_summary"]
        report = analysis["quality_report"]
        assert summary["age_at_capture_seconds"] == report["freshness"]["age_at_capture_seconds"]
        assert summary["limitations_note"] == report["limitations_note"]


class TestGuardrails:
    def test_guardrails_present_and_non_claiming(self, analysis) -> None:
        guardrails = analysis["guardrails"]
        assert guardrails
        text = " ".join(guardrails).lower()
        for term in ("correlation", "causality", "market coverage", "representative", "keyword evidence"):
            assert term in text
        # Toda salvaguarda que menciona una afirmación debe negarla.
        for guardrail in guardrails:
            lowered = guardrail.lower()
            if any(term in lowered for term in ("correlation", "causality", "market", "represent")):
                assert "not" in lowered

    def test_no_evidence_distinction_in_guardrails(self, analysis) -> None:
        assert any("no_evidence" in g and "not evidence" in g for g in analysis["guardrails"])

    def test_limitations_propagated(self, analysis, dataset) -> None:
        assert analysis["limitations"] == dataset["sample"]["limitations"]

    def test_streamlit_still_pending(self, analysis) -> None:
        assert "pending" in analysis["streamlit_status"].lower()
        assert "streamlit" in analysis["streamlit_status"].lower()


class TestRejection:
    def test_wrong_kind_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["dataset_kind"] = "full_feed"
        with pytest.raises(DescriptiveError, match="development_sample"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_wrong_record_count_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["sample"]["records"] = 21
        with pytest.raises(DescriptiveError, match="20"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_wrong_page_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["sample"]["page"] = 2
        with pytest.raises(DescriptiveError, match="page"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_wrong_offset_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["sample"]["offset"] = 20
        with pytest.raises(DescriptiveError, match="offset"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_wrong_limit_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["sample"]["limit"] = 40
        with pytest.raises(DescriptiveError, match="limit"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_different_snapshot_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["capture_identity"]["snapshot_id"] = "cap_0000000000000000"
        with pytest.raises(DescriptiveError, match="snapshot"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_complete_true_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["sample"]["complete"] = True
        with pytest.raises(DescriptiveError, match="complete"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_mismatched_taxonomy_version_rejected(self, dataset) -> None:
        doc = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        doc["version"] = "technical-skills-9.9.9"
        other = taxonomy_from_dict(doc)
        with pytest.raises(DescriptiveError, match="versión de la taxonomía"):
            validate_development_sample(dataset, other)

    def test_build_rejects_invalid_dataset(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["sample"]["complete"] = True
        with pytest.raises(DescriptiveError):
            build_descriptive_analysis(modified, load_taxonomy(TAXONOMY_PATH))


class TestDeterminism:
    def test_build_is_deterministic(self, dataset, taxonomy) -> None:
        first = build_descriptive_analysis(dataset, taxonomy)
        second = build_descriptive_analysis(dataset, taxonomy)
        assert first == second
        assert serialize_analysis(first) == serialize_analysis(second)

    def test_serialization_has_trailing_newline(self, analysis) -> None:
        data = serialize_analysis(analysis)
        assert data.endswith(b"\n")
        assert json.loads(data.decode("utf-8"))["snapshot_id"] == SNAPSHOT_ID


class TestSummaryHelper:
    def test_quality_freshness_summary_contract(self, dataset) -> None:
        summary = quality_freshness_summary(dataset)
        assert set(summary) == {
            "record_count",
            "checked_fields",
            "missing_field_counts",
            "duplicate_source_id_records",
            "observation_status_counts",
            "records_with_evidence",
            "records_without_evidence",
            "no_evidence_record_ids",
            "age_at_capture_seconds",
            "freshness_formula",
            "limitations_note",
        }
        assert summary["checked_fields"] == ["title_raw", "excerpt_raw", "categories_raw", "description_html_raw"]


class TestTriangulate:
    """Casos límite que protegen materialmente el contrato de agregación."""

    def test_record_count_mismatch_rejected(self, dataset) -> None:
        modified = copy.deepcopy(dataset)
        modified["records"] = modified["records"][:10]
        with pytest.raises(DescriptiveError, match="registros"):
            validate_development_sample(modified, load_taxonomy(TAXONOMY_PATH))

    def test_no_evidence_record_contributes_nothing(self, taxonomy) -> None:
        records = [
            {"skill_evidence": {"evidence_status": "no_evidence", "skills": []}},
            {"skill_evidence": {"skills": ["skill.ai"]}},
        ]
        assert skill_frequency(records) == {"skill.ai": 1}
        assert cooccurrence_pairs(records)["pairs"] == []
        categories = {c["category"]: c for c in category_coverage(records, taxonomy)["categories"]}
        assert categories["ml_ai"]["records"] == 1

    def test_unknown_skill_id_ignored_in_category_and_matrix(self, taxonomy) -> None:
        records = [{"skill_evidence": {"skills": ["skill.ai", "skill.not_in_taxonomy"]}}]
        categories = {c["category"]: c for c in category_coverage(records, taxonomy)["categories"]}
        assert categories["ml_ai"]["records"] == 1
        assert categories["ml_ai"]["matched_skills"] == ["skill.ai"]
        # La matriz está acotada a la taxonomía: el id desconocido no tiene fila/columna
        # ni crea ninguna celda. Los pares se calculan sobre los conjuntos de habilidades
        # crudos por registro (agnósticos a la taxonomía por diseño), así que el par sí existe allí.
        matrix_doc = cooccurrence_matrix(records, taxonomy)
        assert "skill.not_in_taxonomy" not in matrix_doc["skill_ids"]
        ids = matrix_doc["skill_ids"]
        ai = ids.index("skill.ai")
        assert all(matrix_doc["matrix"][ai][j] == 0 for j in range(len(ids)))
        assert cooccurrence_pairs(records)["pairs"] == [
            {"skill_a": "skill.ai", "skill_b": "skill.not_in_taxonomy", "records": 1}
        ]
        # La lista de cero coincidencias solo incluye habilidades de la taxonomía; el id desconocido no aparece.
        assert all(
            s["skill_id"] != "skill.not_in_taxonomy"
            for s in zero_match_skills(records, taxonomy)["skills"]
        )

    def test_empty_records_produce_empty_aggregates(self, taxonomy) -> None:
        records: list[dict] = []
        assert skill_frequency(records) == {}
        assert cooccurrence_pairs(records)["pairs"] == []
        matrix_doc = cooccurrence_matrix(records, taxonomy)
        assert matrix_doc["skill_ids"] == sorted(s.skill_id for s in taxonomy.skills)
        assert all(all(cell == 0 for cell in row) for row in matrix_doc["matrix"])
        assert zero_match_skills(records, taxonomy)["count"] == len(taxonomy.skills)

    def test_serialized_artifact_has_guardrails_and_no_raw_text(self, dataset, taxonomy) -> None:
        data = serialize_analysis(build_descriptive_analysis(dataset, taxonomy))
        text = data.decode("utf-8")
        assert "not market coverage" in text
        assert "not correlation" in text
        assert "not causality" in text
        assert "not representative" in text
        assert "no_evidence" in text
        assert '"complete": false' in text
        # El informe de calidad se copia textualmente, así que los NOMBRES de los campos
        # revisados están presentes; los VALORES crudos (texto completo de las descripciones) no deben estarlo.
        raw_text = dataset["records"][0]["description_html_raw"]
        assert raw_text not in text

    def test_serialized_artifact_is_sorted_json(self, dataset, taxonomy) -> None:
        data = serialize_analysis(build_descriptive_analysis(dataset, taxonomy))
        parsed = json.loads(data.decode("utf-8"))
        assert list(parsed) == sorted(parsed)
        assert parsed["sample"]["complete"] is False
        assert parsed["snapshot_id"] == SNAPSHOT_ID

    def test_all_taxonomy_categories_covered_by_definition(self, dataset, taxonomy) -> None:
        analysis = build_descriptive_analysis(dataset, taxonomy)
        covered = {c["category"] for c in analysis["category_coverage"]["categories"]}
        assert covered == set(taxonomy.categories)
