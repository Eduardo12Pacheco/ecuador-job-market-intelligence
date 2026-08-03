"""Pruebas offline de la revisión independiente de etiquetas de habilidades de segunda pasada.

La segunda pasada consume SOLO el conjunto de datos analítico confirmado
(``data/analytics/development-sample-0.1.0.json``), el artefacto de taxonomía
versionado y el primer artefacto de evaluación en borrador — nunca páginas
crudas, manifiestos, respuestas de API ni red, y nunca los comandos de
verificación finales del padre. La fecha de anotación es la fecha fija del
repositorio ``2026-08-02``.

Contratos bajo prueba:

- ``annotate_second_pass(...)`` etiqueta los 740 pares (20 x 37) leyendo los
  campos de texto fuente de un manifiesto de adjudicación curado y NUNCA lee
  ``skill_evidence`` (la independencia se prueba eliminando la salida del
  matcher de una copia del conjunto de datos y afirmando etiquetas idénticas);
- el artefacto confirmado ``skill-extraction-review-0.2.0.json`` declara
  ``annotation_status: draft_second_pass`` y ``human_review_required: true`` y
  nunca es ``gold`` / ``human_reviewed``;
- validación de esquema: enum de etiquetas cerrado, sin etiquetas duplicadas,
  cobertura completa exacta de 740 pares, coincidencia de metadatos
  (instantánea, taxonomía, tipo de conjunto de datos, forma de la muestra,
  advertencia de no cobertura de mercado), citas/offsets de evidencia exactos;
- ``supported`` requiere evidencia; ``not_supported`` tiene evidencia vacía más
  ``reviewed_fields`` y una razón; ``uncertain`` lleva la cita ambigua cuando
  existe texto más una ``human_review_question``;
- la comparación primera-vs-segunda es determinista: 57 acuerdos / 3
  desacuerdos sobre los 60 pares del primer borrador, 680 pares sin etiquetar
  en el primer borrador y una cola de revisión humana deduplicada con todas las
  etiquetas uncertain de la segunda pasada más los desacuerdos (7 elementos);
- comparación con el matcher sobre etiquetas no inciertas: TP/FP/FN/TN =
  38/13/0/684, precisión 38/51, recall 1.0, F1 76/89, macro sobre un alcance
  explícito de 37 habilidades con 4 habilidades excluidas por indefinidas,
  uncertain (5) excluidas de los denominadores primarios, pares predichos sin
  etiquetar = 0;
- cobertura 740/740 pares y 20/20 registros; conteo de registros sin evidencia 0;
- serialización determinista, bytes canónicos del artefacto, materialización
  idempotente, rechazo de sobrescritura y ninguna descripción cruda completa en
  ningún lugar.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from job_market_intelligence.analysis.errors import DatasetError, EvaluationError
from job_market_intelligence.analysis.evaluation import (
    ANNOTATION_DATE,
    DATASET_TYPE,
    EVALUATION_ARTIFACT_DEFAULT_PATH,
    EVIDENCE_FIELDS,
    LABEL_VALUES,
    SAMPLE_LIMIT,
    SAMPLE_OFFSET,
    SAMPLE_PAGE,
    SAMPLE_RECORDS,
    SNAPSHOT_ID,
    load_evaluation,
    resolve_quote_span,
)
from job_market_intelligence.analysis.review import (
    REVIEW_ARTIFACT_DEFAULT_PATH,
    REVIEW_REPORT_DEFAULT_PATH,
    materialize_second_pass_review,
)
from job_market_intelligence.analysis.second_pass import (
    REVIEWED_FIELDS,
    REVIEW_VERSION,
    annotate_second_pass,
    build_second_pass_doc,
    build_second_pass_report,
    compare_first_vs_second,
    compare_with_predictions,
    load_second_pass_review,
    second_pass_from_dict,
    serialize_second_pass,
    serialize_second_pass_report,
    validate_second_pass,
)
from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    load_taxonomy,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "data" / "analytics" / "development-sample-0.1.0.json"
TAXONOMY_PATH = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH
FIRST_PASS_PATH = REPO_ROOT / EVALUATION_ARTIFACT_DEFAULT_PATH
SECOND_PASS_PATH = REPO_ROOT / REVIEW_ARTIFACT_DEFAULT_PATH

# Números esperados exactos para la revisión de segunda pasada confirmada (derivados del
# manifiesto de adjudicación independiente; ver docs/evaluation-review.md).
EXPECTED = {
    "labels_total": 740,
    "supported": 38,
    "not_supported": 697,
    "uncertain": 5,
    "non_uncertain": 735,
    "total_pairs": 740,
    "annotated_records": 20,
    "tp": 38,
    "fp": 13,
    "fn": 0,
    "tn": 684,
    "precision": 38 / 51,
    "recall": 1.0,
    "f1": 76 / 89,
    "macro_precision": 515 / 528,
    "macro_recall": 1.0,
    "macro_f1": 614 / 627,
    "predicted_pairs": 56,
    "unlabeled_predicted_pairs": 0,
    "first_draft_labels": 60,
    "agreements": 57,
    "disagreements": 3,
    "first_draft_unlabeled_pairs": 680,
    "review_queue": 7,
}

# Los tres desacuerdos reales de primera-vs-segunda (nombre corto de fuente -> ids).
DISAGREEMENT_PAIRS = {
    ("data-tools", "skill.ai"),
    ("mandarin", "skill.ai"),
    ("mandarin", "skill.machine_learning"),
}

# Todos los pares uncertain de la segunda pasada (nombres cortos).
UNCERTAIN_PAIRS = {
    ("german", "skill.machine_learning"),
    ("data-tools", "skill.data_science"),
    ("mandarin", "skill.ai"),
    ("brazil", "skill.ai"),
    ("strategy-ops", "skill.ai"),
}

# Nombre corto -> id de fuente completo de los registros involucrados en desacuerdos/inciertos.
SOURCE_IDS = {
    "german": "https://himalayas.app/companies/micro1/jobs/german-audio-recording-expert",
    "data-tools": "https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist",
    "mandarin": "https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert",
    "brazil": "https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-brazil",
    "strategy-ops": "https://himalayas.app/companies/bjak/jobs/strategy-operations-associate-7652220692",
}

UNCERTAIN_FULL = {(SOURCE_IDS[a], b) for a, b in UNCERTAIN_PAIRS}
DISAGREEMENT_FULL = {(SOURCE_IDS[a], b) for a, b in DISAGREEMENT_PAIRS}


@pytest.fixture(scope="session")
def dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def taxonomy():
    return load_taxonomy(TAXONOMY_PATH)


@pytest.fixture(scope="session")
def first_pass():
    return load_evaluation(FIRST_PASS_PATH)


@pytest.fixture(scope="session")
def second_pass():
    return load_second_pass_review(SECOND_PASS_PATH)


@pytest.fixture(scope="session")
def second_pass_doc() -> dict:
    return json.loads(SECOND_PASS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Anotación independiente.
# ---------------------------------------------------------------------------


class TestAnnotate:
    def test_annotation_covers_exactly_740_unique_pairs(self, dataset, taxonomy) -> None:
        labels = annotate_second_pass(dataset, taxonomy)
        assert len(labels) == EXPECTED["labels_total"]
        pairs = [(label.source_id, label.skill_id) for label in labels]
        assert len(set(pairs)) == EXPECTED["labels_total"]
        expected_pairs = {
            (record["source_id"], skill.skill_id)
            for record in dataset["records"]
            for skill in taxonomy.skills
        }
        assert set(pairs) == expected_pairs

    def test_annotation_never_reads_matcher_predictions(self, dataset, taxonomy) -> None:
        stripped = copy.deepcopy(dataset)
        for record in stripped["records"]:
            record.pop("skill_evidence", None)
        assert annotate_second_pass(stripped, taxonomy) == annotate_second_pass(dataset, taxonomy)

    def test_annotation_is_deterministic_and_sorted(self, dataset, taxonomy) -> None:
        first = annotate_second_pass(dataset, taxonomy)
        second = annotate_second_pass(dataset, taxonomy)
        assert first == second
        keys = [(label.source_id, label.skill_id) for label in first]
        assert keys == sorted(keys)

    def test_annotation_label_distribution(self, dataset, taxonomy) -> None:
        labels = annotate_second_pass(dataset, taxonomy)
        counts = {"supported": 0, "not_supported": 0, "uncertain": 0}
        for label in labels:
            counts[label.label] += 1
        assert counts == {
            "supported": EXPECTED["supported"],
            "not_supported": EXPECTED["not_supported"],
            "uncertain": EXPECTED["uncertain"],
        }

    def test_every_supported_uncertain_evidence_quote_resolves_exactly(self, dataset, taxonomy) -> None:
        record_by_source = {record["source_id"]: record for record in dataset["records"]}
        for label in annotate_second_pass(dataset, taxonomy):
            for ev in label.evidence:
                value = record_by_source[label.source_id][ev.field]
                assert isinstance(value, str)
                assert ev.char_start >= 0 and ev.char_end <= len(value)
                assert value[ev.char_start:ev.char_end] == ev.exact_quote
                assert len(ev.exact_quote) <= 100

    def test_negative_requirement_cases_documented(self, dataset, taxonomy) -> None:
        labels = annotate_second_pass(dataset, taxonomy)
        german_ai = next(
            label
            for label in labels
            if label.source_id == SOURCE_IDS["german"] and label.skill_id == "skill.ai"
        )
        assert german_ai.label == "not_supported"
        assert "No prior experience in AI is required" in german_ai.reason
        assert german_ai.reviewed_fields == REVIEWED_FIELDS

    def test_boundary_cases_documented(self, dataset, taxonomy) -> None:
        labels = annotate_second_pass(dataset, taxonomy)
        by_pair = {(label.source_id, label.skill_id): label for label in labels}
        git_boundary = by_pair[(SOURCE_IDS["data-tools"], "skill.git")]
        assert git_boundary.label == "not_supported"
        assert "GitHub" in git_boundary.reason and "git" in git_boundary.reason


# ---------------------------------------------------------------------------
# Esquema del artefacto y estado draft_second_pass.
# ---------------------------------------------------------------------------


class TestSchema:
    def test_committed_artifact_schema_and_status(self, second_pass) -> None:
        assert second_pass.evaluation_version == REVIEW_VERSION
        assert second_pass.annotation_status == "draft_second_pass"
        assert second_pass.human_review_required is True
        assert second_pass.dataset_type == DATASET_TYPE
        assert second_pass.snapshot_id == SNAPSHOT_ID
        assert second_pass.taxonomy_version == "technical-skills-0.1.0"
        assert second_pass.source == "himalayas"
        assert second_pass.attribution_url == "https://himalayas.app"
        assert second_pass.annotation_date == ANNOTATION_DATE
        assert "independently" in second_pass.annotation_method.lower()
        assert "NOT gold" in second_pass.annotation_method
        sample = second_pass.sample
        assert sample["records"] == SAMPLE_RECORDS
        assert sample["page"] == SAMPLE_PAGE
        assert sample["limit"] == SAMPLE_LIMIT
        assert sample["offset"] == SAMPLE_OFFSET
        assert sample["complete"] is False
        assert "market" in sample["warning"]
        assert len(second_pass.labels) == EXPECTED["labels_total"]

    def test_artifact_never_claims_gold_or_human_reviewed(self, second_pass_doc) -> None:
        assert second_pass_doc["annotation_status"] == "draft_second_pass"
        assert second_pass_doc["human_review_required"] is True
        assert "evaluation_status" not in second_pass_doc
        assert "human_reviewed" not in second_pass_doc
        assert "gold" not in json.dumps(second_pass_doc.get("evaluation_status", ""))

    def test_annotation_status_closed(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        for bad in ("gold", "human_reviewed", "draft_evaluation", "final"):
            mutated = {**doc, "annotation_status": bad}
            with pytest.raises(EvaluationError):
                second_pass_from_dict(mutated)

    def test_forbidden_status_claims_rejected(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        for mutate in (
            {"evaluation_status": "gold"},
            {"evaluation_status": "human_reviewed"},
            {"human_reviewed": True},
            {"human_reviewed": "yes"},
        ):
            with pytest.raises(EvaluationError):
                second_pass_from_dict({**doc, **mutate})

    def test_human_review_required_must_be_true(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        with pytest.raises(EvaluationError):
            second_pass_from_dict({**doc, "human_review_required": False})

    def test_label_enum_closed(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        doc["labels"][0]["label"] = "gold"
        with pytest.raises(EvaluationError):
            second_pass_from_dict(doc)
        assert set(LABEL_VALUES) == {"supported", "not_supported", "uncertain"}

    def test_duplicate_labels_rejected(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        doc["labels"].append(copy.deepcopy(doc["labels"][0]))
        with pytest.raises(EvaluationError):
            second_pass_from_dict(doc)

    def test_complete_740_coverage_enforced(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        with pytest.raises(EvaluationError):
            second_pass_from_dict({**doc, "labels": doc["labels"][:-1]})

    def test_every_label_has_reason_and_not_supported_reviewed_fields(self, second_pass) -> None:
        for label in second_pass.labels:
            assert isinstance(label.reason, str) and label.reason.strip()
            assert label.reviewed_fields == REVIEWED_FIELDS
            if label.label == "not_supported":
                assert label.evidence == ()
            if label.label == "uncertain":
                assert isinstance(label.human_review_question, str) and label.human_review_question.strip()

    def test_supported_requires_evidence(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        doc["labels"][0]["evidence"] = []
        with pytest.raises(EvaluationError):
            second_pass_from_dict(doc)

    def test_not_supported_must_have_empty_evidence(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        ns = next(label for label in doc["labels"] if label["label"] == "not_supported")
        ns["evidence"] = [
            {"field": "title_raw", "exact_quote": "x", "char_start": 0, "char_end": 1}
        ]
        with pytest.raises(EvaluationError):
            second_pass_from_dict(doc)

    def test_missing_required_metadata_rejected(self, dataset) -> None:
        doc = build_second_pass_doc(dataset, load_taxonomy(TAXONOMY_PATH))
        del doc["annotation_method"]
        with pytest.raises(EvaluationError):
            second_pass_from_dict(doc)


# ---------------------------------------------------------------------------
# Validación cruzada contra el conjunto de datos y la taxonomía.
# ---------------------------------------------------------------------------


class TestCrossValidation:
    def test_committed_artifact_validates_against_dataset(self, second_pass, dataset, taxonomy) -> None:
        validate_second_pass(second_pass, dataset, taxonomy)  # no debe lanzar excepción

    def test_unknown_source_id_rejected(self, second_pass, dataset, taxonomy) -> None:
        labels = list(second_pass.labels)
        first = labels[0]
        labels[0] = first.__class__(
            source_id="https://himalayas.app/jobs/not-in-dataset",
            skill_id=first.skill_id,
            label=first.label,
            evidence=first.evidence,
            reviewed_fields=first.reviewed_fields,
            reason=first.reason,
            human_review_question=first.human_review_question,
            notes=first.notes,
        )
        bad = second_pass.__class__(
            evaluation_version=second_pass.evaluation_version,
            evaluation_kind=second_pass.evaluation_kind,
            annotation_status=second_pass.annotation_status,
            human_review_required=second_pass.human_review_required,
            dataset_type=second_pass.dataset_type,
            dataset_version=second_pass.dataset_version,
            snapshot_id=second_pass.snapshot_id,
            taxonomy_version=second_pass.taxonomy_version,
            matcher_version=second_pass.matcher_version,
            source=second_pass.source,
            endpoint=second_pass.endpoint,
            attribution_url=second_pass.attribution_url,
            annotation_date=second_pass.annotation_date,
            annotation_method=second_pass.annotation_method,
            sample=second_pass.sample,
            labels=tuple(labels),
        )
        with pytest.raises(EvaluationError):
            validate_second_pass(bad, dataset, taxonomy)

    def test_unknown_skill_id_rejected(self, second_pass, dataset, taxonomy) -> None:
        labels = list(second_pass.labels)
        first = labels[0]
        labels[0] = first.__class__(
            source_id=first.source_id,
            skill_id="skill.not_in_taxonomy",
            label=first.label,
            evidence=first.evidence,
            reviewed_fields=first.reviewed_fields,
            reason=first.reason,
            human_review_question=first.human_review_question,
            notes=first.notes,
        )
        bad = second_pass.__class__(
            **{**second_pass.__dict__, "labels": tuple(labels)}
        )
        with pytest.raises(EvaluationError):
            validate_second_pass(bad, dataset, taxonomy)

    def test_snapshot_mismatch_rejected(self, dataset, taxonomy) -> None:
        doc = build_second_pass_doc(dataset, taxonomy)
        with pytest.raises(EvaluationError):
            validate_second_pass(second_pass_from_dict({**doc, "snapshot_id": "cap_other"}), dataset, taxonomy)

    def test_taxonomy_version_mismatch_rejected(self, dataset, taxonomy) -> None:
        doc = build_second_pass_doc(dataset, taxonomy)
        with pytest.raises(EvaluationError):
            validate_second_pass(
                second_pass_from_dict({**doc, "taxonomy_version": "technical-skills-9.9.9"}),
                dataset,
                taxonomy,
            )

    def test_dataset_type_mismatch_rejected(self, dataset, taxonomy) -> None:
        doc = build_second_pass_doc(dataset, taxonomy)
        with pytest.raises(EvaluationError):
            validate_second_pass(second_pass_from_dict({**doc, "dataset_type": "full_feed"}), dataset, taxonomy)

    def test_sample_shape_mismatch_rejected(self, dataset, taxonomy) -> None:
        doc = build_second_pass_doc(dataset, taxonomy)
        with pytest.raises(EvaluationError):
            validate_second_pass(
                second_pass_from_dict(
                    {**doc, "sample": {**doc["sample"], "records": 19}}
                ),
                dataset,
                taxonomy,
            )

    def test_evidence_offsets_and_quotes_validated_exactly(self, dataset, taxonomy) -> None:
        doc = build_second_pass_doc(dataset, taxonomy)
        entry = next(label for label in doc["labels"] if label["evidence"])
        ev = entry["evidence"][0]
        field = ev["field"]
        for mutated in (
            {**ev, "char_start": ev["char_start"] + 1},
            {**ev, "char_end": ev["char_end"] - 1},
            {**ev, "exact_quote": "not the real quote"},
        ):
            entry["evidence"] = [mutated]
            with pytest.raises(EvaluationError):
                validate_second_pass(second_pass_from_dict(doc), dataset, taxonomy)


# ---------------------------------------------------------------------------
# Comparación del primer borrador contra la segunda pasada.
# ---------------------------------------------------------------------------


class TestFirstVsSecond:
    def test_exact_agreement_and_disagreement_counts(self, first_pass, second_pass) -> None:
        comp = compare_first_vs_second(first_pass, second_pass)
        assert comp["first_draft_labels"] == EXPECTED["first_draft_labels"]
        assert comp["second_pass_labels"] == EXPECTED["labels_total"]
        assert comp["overlapping_pairs"] == EXPECTED["first_draft_labels"]
        assert comp["agreements"] == EXPECTED["agreements"]
        assert comp["disagreements"] == EXPECTED["disagreements"]
        assert comp["first_draft_unlabeled_pairs"] == EXPECTED["first_draft_unlabeled_pairs"]

    def test_exact_disagreement_pairs(self, first_pass, second_pass) -> None:
        comp = compare_first_vs_second(first_pass, second_pass)
        got = {(entry["source_id"], entry["skill_id"]) for entry in comp["disagreement_list"]}
        assert got == DISAGREEMENT_FULL

    def test_per_skill_breakdown(self, first_pass, second_pass) -> None:
        comp = compare_first_vs_second(first_pass, second_pass)
        assert comp["per_skill"]["skill.ai"] == {
            "first_draft_labels": 11,
            "agreements": 9,
            "disagreements": 2,
        }
        assert comp["per_skill"]["skill.machine_learning"] == {
            "first_draft_labels": 4,
            "agreements": 3,
            "disagreements": 1,
        }
        assert sum(skill["first_draft_labels"] for skill in comp["per_skill"].values()) == 60

    def test_human_review_queue_is_uncertain_plus_disagreements(self, first_pass, second_pass) -> None:
        comp = compare_first_vs_second(first_pass, second_pass)
        queue = comp["human_review_queue"]
        assert queue["count"] == EXPECTED["review_queue"]
        assert queue["note"] and "uncertain" in queue["note"] and "disagreement" in queue["note"]
        queued = {(entry["source_id"], entry["skill_id"]) for entry in queue["items"]}
        assert queued == UNCERTAIN_FULL | DISAGREEMENT_FULL
        for entry in queue["items"]:
            assert entry["reason"]
            if entry["second_pass_label"] == "uncertain":
                assert entry["human_review_question"]

    def test_comparison_deterministic(self, first_pass, second_pass) -> None:
        assert compare_first_vs_second(first_pass, second_pass) == compare_first_vs_second(
            first_pass, second_pass
        )


# ---------------------------------------------------------------------------
# Comparación con el matcher y métricas.
# ---------------------------------------------------------------------------


class TestMetricsVsMatcher:
    def test_exact_contingency(self, second_pass, dataset, taxonomy) -> None:
        cont = compare_with_predictions(second_pass, dataset, taxonomy)
        assert cont["tp"] == EXPECTED["tp"]
        assert cont["fp"] == EXPECTED["fp"]
        assert cont["fn"] == EXPECTED["fn"]
        assert cont["tn"] == EXPECTED["tn"]
        assert cont["uncertain"] == EXPECTED["uncertain"]
        assert cont["labeled_pairs"] == EXPECTED["labels_total"]
        assert cont["non_uncertain_labeled_pairs"] == EXPECTED["non_uncertain"]
        assert cont["unlabeled_predicted_pairs"] == EXPECTED["unlabeled_predicted_pairs"]

    def test_all_false_positives_are_negation_limited_ai_predictions(self, second_pass, dataset, taxonomy) -> None:
        cont = compare_with_predictions(second_pass, dataset, taxonomy)
        assert len(cont["false_positives"]) == EXPECTED["fp"]
        assert {entry["skill_id"] for entry in cont["false_positives"]} == {"skill.ai"}
        for entry in cont["false_positives"]:
            assert entry["label"] == "not_supported"
            me = entry["matcher_evidence"]
            assert me["field"] in EVIDENCE_FIELDS
            assert me["matched_term"] == "ai"
            assert entry["reason"]

    def test_no_false_negatives_in_curated_set(self, second_pass, dataset, taxonomy) -> None:
        cont = compare_with_predictions(second_pass, dataset, taxonomy)
        assert cont["false_negatives"] == []

    def test_exact_primary_metrics(self, second_pass, dataset, taxonomy) -> None:
        metrics = compare_with_predictions(second_pass, dataset, taxonomy)["metrics"]
        primary = metrics["primary"]
        assert primary["tp"] == EXPECTED["tp"]
        assert primary["fp"] == EXPECTED["fp"]
        assert primary["fn"] == EXPECTED["fn"]
        assert primary["tn"] == EXPECTED["tn"]
        assert primary["precision"] == pytest.approx(EXPECTED["precision"])
        assert primary["recall"] == pytest.approx(EXPECTED["recall"])
        assert primary["f1"] == pytest.approx(EXPECTED["f1"])
        assert metrics["uncertain"]["count"] == EXPECTED["uncertain"]

    def test_macro_scope_explicit(self, second_pass, dataset, taxonomy) -> None:
        metrics = compare_with_predictions(second_pass, dataset, taxonomy)["metrics"]
        macro = metrics["macro"]
        assert len(macro["skills_in_scope"]) == 37
        assert macro["skills_excluded_undefined"] == [
            "skill.cpp",
            "skill.csharp",
            "skill.git",
            "skill.java",
        ]
        assert macro["precision"] == pytest.approx(EXPECTED["macro_precision"])
        assert macro["recall"] == pytest.approx(EXPECTED["macro_recall"])
        assert macro["f1"] == pytest.approx(EXPECTED["macro_f1"])
        assert macro["per_skill"]["skill.ai"] == {
            "tp": 3, "fp": 13, "fn": 0, "tn": 1,
            "precision": pytest.approx(3 / 16), "recall": 1.0, "f1": pytest.approx(6 / 19),
        }

    def test_uncertain_excluded_from_primary_metrics(self, second_pass, dataset, taxonomy) -> None:
        metrics = compare_with_predictions(second_pass, dataset, taxonomy)["metrics"]
        assert metrics["uncertain"]["count"] == EXPECTED["uncertain"]
        assert metrics["uncertain"]["excluded_note"]
        assert "excluded" in metrics["uncertain"]["excluded_note"]

    def test_predictions_dedup_per_record(self, second_pass, dataset, taxonomy) -> None:
        cont = compare_with_predictions(second_pass, dataset, taxonomy)
        assert cont["predicted_pairs"] == EXPECTED["predicted_pairs"]


# ---------------------------------------------------------------------------
# Informe, cobertura, determinismo y materialización.
# ---------------------------------------------------------------------------


class TestReport:
    def test_coverage_is_complete(self, second_pass, dataset, taxonomy) -> None:
        report = build_second_pass_report(
            load_evaluation(FIRST_PASS_PATH), second_pass, dataset, taxonomy
        )
        coverage = report["coverage"]
        assert coverage["labeled_pairs"] == 740
        assert coverage["total_pairs"] == 740
        assert coverage["pair_coverage"] == 1.0
        assert coverage["non_uncertain_labeled_pairs"] == EXPECTED["non_uncertain"]
        assert coverage["annotated_records"] == 20
        assert coverage["annotated_record_coverage"] == 1.0

    def test_report_sections_and_guardrails(self, second_pass, dataset, taxonomy) -> None:
        report = build_second_pass_report(
            load_evaluation(FIRST_PASS_PATH), second_pass, dataset, taxonomy
        )
        assert report["evaluation_version"] == REVIEW_VERSION
        assert report["annotation_status"] == "draft_second_pass"
        assert report["human_review_required"] is True
        assert report["snapshot_id"] == SNAPSHOT_ID
        assert report["sample"]["records"] == 20
        assert report["sample"]["complete"] is False
        assert report["metrics"]["primary"]["tp"] == EXPECTED["tp"]
        assert report["label_distribution"]["second_pass"]["supported"] == EXPECTED["supported"]
        assert report["label_distribution"]["first_draft"]["supported"] == 38
        assert report["record_summary"]["records_reviewed"] == 20
        assert report["record_summary"]["records_without_evidence"] == 0
        assert any("human review" in w for w in report["warnings"])
        assert any("market" in l for l in report["limitations"])
        assert any("not gold" in g or "not gold" in g for g in report["guardrails"])

    def test_report_deterministic_repeated_output(self, first_pass, second_pass, dataset, taxonomy) -> None:
        first = build_second_pass_report(first_pass, second_pass, dataset, taxonomy)
        second = build_second_pass_report(first_pass, second_pass, dataset, taxonomy)
        assert first == second
        assert serialize_second_pass_report(first) == serialize_second_pass_report(second)

    def test_committed_artifact_is_canonical_and_matches_annotation(self, dataset, taxonomy) -> None:
        doc = json.loads(SECOND_PASS_PATH.read_text(encoding="utf-8"))
        canonical = json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        assert SECOND_PASS_PATH.read_text(encoding="utf-8") == canonical
        assert serialize_second_pass(doc) == canonical.encode("utf-8")
        assert serialize_second_pass(doc) == serialize_second_pass(
            build_second_pass_doc(dataset, taxonomy)
        )

    def test_no_full_raw_descriptions_in_artifacts(self, second_pass, dataset, taxonomy) -> None:
        doc = json.loads(SECOND_PASS_PATH.read_text(encoding="utf-8"))
        report = build_second_pass_report(
            load_evaluation(FIRST_PASS_PATH), second_pass, dataset, taxonomy
        )
        banned = ("micro1 is engaging", "Originally posted on", "Scope of Work", "<p>", "<h3>")

        def walk(node):
            if isinstance(node, dict):
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
            elif isinstance(node, str):
                for fragment in banned:
                    assert fragment not in node, f"el fragmento de descripción cruda {fragment!r} se filtró"

        walk(doc)
        walk(report)
        for label in second_pass.labels:
            for ev in label.evidence:
                assert len(ev.exact_quote) <= 100


class TestMaterialize:
    def test_materialize_writes_both_artifacts_and_is_idempotent(self, tmp_path) -> None:
        artifact_out = tmp_path / "review.json"
        report_out = tmp_path / "report.json"
        materialize_second_pass_review(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            first_pass_path=FIRST_PASS_PATH,
            artifact_output_path=artifact_out,
            report_output_path=report_out,
        )
        assert artifact_out.read_bytes() == SECOND_PASS_PATH.read_bytes()
        dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        taxonomy = load_taxonomy(TAXONOMY_PATH)
        second_pass = load_second_pass_review(SECOND_PASS_PATH)
        expected_report = serialize_second_pass_report(
            build_second_pass_report(load_evaluation(FIRST_PASS_PATH), second_pass, dataset, taxonomy)
        )
        assert report_out.read_bytes() == expected_report
        materialize_second_pass_review(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            first_pass_path=FIRST_PASS_PATH,
            artifact_output_path=artifact_out,
            report_output_path=report_out,
        )  # no-op a nivel de bytes: no debe lanzar excepción

    def test_materialize_refuses_overwrite_with_different_content(self, tmp_path) -> None:
        artifact_out = tmp_path / "review.json"
        artifact_out.write_text('{"stale": true}', encoding="utf-8")
        with pytest.raises(DatasetError):
            materialize_second_pass_review(
                dataset_path=DATASET_PATH,
                taxonomy_path=TAXONOMY_PATH,
                first_pass_path=FIRST_PASS_PATH,
                artifact_output_path=artifact_out,
                report_output_path=tmp_path / "report.json",
            )
