"""Pruebas offline del hito de evaluación del borrador de extracción de habilidades.

La evaluación consume SOLO el conjunto de datos analítico confirmado
(``data/analytics/development-sample-0.1.0.json``), el artefacto de taxonomía
versionado (``data/taxonomy/technical-skills-0.1.0.json``) y el artefacto de
evaluación en borrador confirmado
(``data/evaluation/skill-extraction-development-0.1.0.json``). No intervienen
páginas crudas, manifiestos, respuestas de API ni red, y no se consulta el
reloj de pared: la fecha de anotación es la fecha fija del repositorio
``2026-08-02``.

Contratos bajo prueba:

- el artefacto de evaluación es un ``draft_evaluation`` (nunca ``gold`` ni
  ``human_reviewed``) con los metadatos documentados exactos (versión de
  evaluación, tipo de conjunto de datos, id de instantánea, versión de
  taxonomía, fuente, atribución, fecha de anotación, forma de la muestra);
- el enum de etiquetas es cerrado y se rechazan las etiquetas duplicadas
  ``(source_id, skill_id)``;
- se rechazan ids de fuente desconocidos / ids de habilidad desconocidos /
  desajustes de instantánea / taxonomía / tipo de conjunto de datos;
- las citas y los offsets de evidencia se validan exactamente contra el valor
  del campo del conjunto de datos (``field[char_start:char_end] == exact_quote``;
  límites; offsets no negativos; solo campos de texto);
- las etiquetas ``supported`` requieren al menos una entrada de evidencia
  exacta; las etiquetas ``not_supported`` tienen evidencia vacía; las
  etiquetas ``uncertain`` están permitidas pero excluidas de las métricas
  primarias;
- la contingencia exacta TP/FP/FN/TN (una habilidad predicha cuenta como
  máximo una vez por registro; los pares sin etiquetar se excluyen, nunca se
  tratan como negativos);
- precisión/recall/F1 con denominadores cero seguros;
- métricas micro y macro con un alcance determinista explícito;
- conjuntos vacíos / sin predicciones;
- serialización determinista y salida de informe repetida;
- evidencia exacta en las entradas de error FP/FN;
- ninguna descripción cruda completa en los artefactos de evaluación/informe.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from job_market_intelligence.analysis.errors import DatasetError, EvaluationError
from job_market_intelligence.analysis.evaluate import materialize_evaluation_report
from job_market_intelligence.analysis.evaluation import (
    ANNOTATION_DATE,
    DATASET_TYPE,
    EVALUATION_ARTIFACT_DEFAULT_PATH,
    EVALUATION_KIND,
    EVALUATION_STATUS,
    EVALUATION_VERSION,
    EVIDENCE_FIELDS,
    LABEL_VALUES,
    SAMPLE_LIMIT,
    SAMPLE_OFFSET,
    SAMPLE_PAGE,
    SAMPLE_RECORDS,
    SNAPSHOT_ID,
    build_contingency,
    build_report,
    compute_metrics,
    evaluation_from_dict,
    load_evaluation,
    predictions_by_record,
    resolve_quote_span,
    serialize_evaluation,
    serialize_report,
    validate_evaluation,
)
from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    load_taxonomy,
    taxonomy_from_dict,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "data" / "analytics" / "development-sample-0.1.0.json"
TAXONOMY_PATH = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH
EVALUATION_PATH = REPO_ROOT / EVALUATION_ARTIFACT_DEFAULT_PATH

# Números esperados exactos para el artefacto en borrador confirmado (derivados a mano de
# los campos fuente revisados; ver el annotation_method del artefacto).
EXPECTED = {
    "tp": 38,
    "fp": 5,
    "fn": 0,
    "tn": 13,
    "uncertain": 4,
    "labels_total": 60,
    "non_uncertain": 56,
    "total_pairs": 740,
    "unlabeled_predicted_pairs": 10,
    "predicted_pairs": 56,
    "annotated_records": 11,
    "precision": 38 / 43,
    "recall": 1.0,
    "f1": 76 / 81,
    "macro_precision": (3 / 8 + 32) / 33,
    "macro_recall": 1.0,
    "macro_f1": (32 + 6 / 11) / 33,
}


@pytest.fixture(scope="session")
def dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def taxonomy():
    return load_taxonomy(TAXONOMY_PATH)


@pytest.fixture(scope="session")
def evaluation():
    return load_evaluation(EVALUATION_PATH)


# ---------------------------------------------------------------------------
# Mini accesorios sintéticos para pruebas de aritmética exacta y casos límite.
# ---------------------------------------------------------------------------


def make_taxonomy_doc(skills=("skill.a", "skill.b", "skill.c")):
    return {
        "version": "technical-skills-0.1.0",
        "categories": ["programming_language"],
        "skills": [
            {
                "skill_id": sid,
                "name": sid,
                "category": "programming_language",
                "keywords": [sid.split(".", 1)[1]],
                "aliases": [],
            }
            for sid in skills
        ],
        "rules": {"term_types": "keywords and aliases"},
    }


def make_record(
    source_id: str,
    skills=(),
    *,
    title: str = "Some Title",
    excerpt: str = "Some excerpt",
    description: str = "<p>Some description</p>",
) -> dict:
    return {
        "canonical_id": source_id,
        "source": "himalayas",
        "source_id": source_id,
        "snapshot_id": SNAPSHOT_ID,
        "title_raw": title,
        "excerpt_raw": excerpt,
        "categories_raw": [],
        "description_html_raw": description,
        "skill_evidence": {
            "evidence_status": "matched" if skills else "no_evidence",
            "taxonomy_version": "technical-skills-0.1.0",
            "matcher_version": "keyword-baseline-0.1.0",
            "skills": list(skills),
            "evidence": [
                {
                    "skill_id": skill_id,
                    "field": "title_raw",
                    "matched_term": skill_id.split(".", 1)[1],
                    "term_type": "keyword",
                    "excerpt": title[:40],
                    "occurrence_count": 1,
                }
                for skill_id in skills
            ],
        },
    }


def make_dataset(records, **overrides) -> dict:
    doc = {
        "dataset_version": "0.1.0",
        "dataset_kind": DATASET_TYPE,
        "taxonomy_version": "technical-skills-0.1.0",
        "matcher_version": "keyword-baseline-0.1.0",
        "capture_identity": {
            "source": "himalayas",
            "endpoint": "https://himalayas.app/jobs/api",
            "snapshot_id": SNAPSHOT_ID,
            "attribution_url": "https://himalayas.app",
        },
        "sample": {
            "records": len(records),
            "page": SAMPLE_PAGE,
            "limit": SAMPLE_LIMIT,
            "offset": SAMPLE_OFFSET,
            "complete": False,
        },
        "records": records,
        "quality_report": {
            "record_count": len(records),
            "skill_coverage": {
                "records_with_evidence": 0,
                "records_without_evidence": 0,
                "records_no_evidence": [],
                "skill_counts": {},
            },
        },
    }
    doc.update(overrides)
    return doc


def evidence(record: dict, field: str, quote: str, start: int | None = None, end: int | None = None) -> dict:
    """Construye una entrada de evidencia; los offsets toman por defecto el primer tramo de la cita."""
    value = record[field]
    if start is None:
        span = resolve_quote_span(value, quote)
        assert span is not None, f"la cita {quote!r} no se encontró en {field}"
        start, end = span
    return {"field": field, "exact_quote": quote, "char_start": start, "char_end": end}


def label(source_id: str, skill_id: str, value: str = "supported", evidence_: list | None = None, notes=None) -> dict:
    return {
        "source_id": source_id,
        "skill_id": skill_id,
        "label": value,
        "evidence": evidence_ if evidence_ is not None else [],
        "notes": notes,
    }


def make_evaluation(labels, sample_records: int = SAMPLE_RECORDS, **overrides) -> dict:
    doc = {
        "evaluation_version": EVALUATION_VERSION,
        "evaluation_kind": EVALUATION_KIND,
        "evaluation_status": EVALUATION_STATUS,
        "dataset_type": DATASET_TYPE,
        "dataset_version": "0.1.0",
        "snapshot_id": SNAPSHOT_ID,
        "taxonomy_version": "technical-skills-0.1.0",
        "matcher_version": "keyword-baseline-0.1.0",
        "source": "himalayas",
        "endpoint": "https://himalayas.app/jobs/api",
        "attribution_url": "https://himalayas.app",
        "annotation_date": ANNOTATION_DATE,
        "annotation_method": "draft labels from direct source-text inspection",
        "sample": {
            "records": sample_records,
            "page": SAMPLE_PAGE,
            "limit": SAMPLE_LIMIT,
            "offset": SAMPLE_OFFSET,
            "complete": False,
            "warning": "development sample: not a full feed and not market coverage",
        },
        "labels": labels,
    }
    doc.update(overrides)
    return doc


# ---------------------------------------------------------------------------
# Esquema del artefacto y estado de borrador.
# ---------------------------------------------------------------------------


class TestArtifactSchema:
    def test_committed_artifact_schema_and_draft_status(self, evaluation) -> None:
        assert evaluation.evaluation_version == EVALUATION_VERSION
        assert evaluation.evaluation_kind == EVALUATION_KIND
        assert evaluation.evaluation_status == EVALUATION_STATUS
        assert evaluation.dataset_type == DATASET_TYPE
        assert evaluation.snapshot_id == SNAPSHOT_ID
        assert evaluation.taxonomy_version == "technical-skills-0.1.0"
        assert evaluation.source == "himalayas"
        assert evaluation.attribution_url == "https://himalayas.app"
        assert evaluation.annotation_date == ANNOTATION_DATE
        assert "independently" in evaluation.annotation_method
        assert "human-reviewed" in evaluation.annotation_method or "not human" in evaluation.annotation_method
        sample = evaluation.sample
        assert sample["records"] == SAMPLE_RECORDS
        assert sample["page"] == SAMPLE_PAGE
        assert sample["limit"] == SAMPLE_LIMIT
        assert sample["offset"] == SAMPLE_OFFSET
        assert sample["complete"] is False
        assert len(evaluation.labels) == EXPECTED["labels_total"]

    def test_evaluation_status_closed(self) -> None:
        for bad in ("gold", "human_reviewed", "final"):
            with pytest.raises(EvaluationError):
                evaluation_from_dict(make_evaluation([], evaluation_status=bad))

    def test_label_enum_closed(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        bad = label(rec["source_id"], "skill.ai", value="gold")
        with pytest.raises(EvaluationError):
            evaluation_from_dict(make_evaluation([bad]))
        assert set(LABEL_VALUES) == {"supported", "not_supported", "uncertain"}

    def test_missing_required_metadata_rejected(self) -> None:
        doc = make_evaluation([])
        del doc["annotation_method"]
        with pytest.raises(EvaluationError):
            evaluation_from_dict(doc)

    def test_empty_labels_rejected(self) -> None:
        with pytest.raises(EvaluationError):
            evaluation_from_dict(make_evaluation([]))

    def test_duplicate_labels_rejected(self, dataset) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        docs = [
            label(rec["source_id"], "skill.ai", evidence_=[ev]),
            label(rec["source_id"], "skill.ai", value="uncertain"),
        ]
        with pytest.raises(EvaluationError):
            evaluation_from_dict(make_evaluation(docs))

    def test_evidence_shape_validation(self, dataset) -> None:
        rec = dataset["records"][0]
        base = evidence(rec, "title_raw", rec["title_raw"])
        for mutated in (
            {**base, "char_start": -1},
            {**base, "char_start": 1, "char_end": 0},
            {**base, "exact_quote": ""},
            {**base, "char_start": "3"},
            {"field": "unknown_field", "exact_quote": "x", "char_start": 0, "char_end": 1},
        ):
            doc = make_evaluation([label(rec["source_id"], "skill.ai", evidence_=[mutated])])
            with pytest.raises(EvaluationError):
                evaluation_from_dict(doc)

    def test_supported_requires_evidence(self, dataset) -> None:
        rec = dataset["records"][0]
        with pytest.raises(EvaluationError):
            evaluation_from_dict(make_evaluation([label(rec["source_id"], "skill.ai")]))

    def test_not_supported_must_have_empty_evidence(self, dataset) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        doc = make_evaluation([label(rec["source_id"], "skill.ai", value="not_supported", evidence_=[ev])])
        with pytest.raises(EvaluationError):
            evaluation_from_dict(doc)


class TestCrossValidation:
    def test_unknown_source_id_rejected(self, dataset, taxonomy) -> None:
        ev = evidence(dataset["records"][0], "title_raw", dataset["records"][0]["title_raw"])
        doc = make_evaluation([label("https://himalayas.app/jobs/not-in-dataset", "skill.ai", evidence_=[ev])])
        evaluation = evaluation_from_dict(doc)
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, dataset, taxonomy)

    def test_unknown_skill_id_rejected(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        doc = make_evaluation([label(rec["source_id"], "skill.not_in_taxonomy", evidence_=[ev])])
        evaluation = evaluation_from_dict(doc)
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, dataset, taxonomy)

    def test_snapshot_mismatch_rejected(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        doc = make_evaluation([label(rec["source_id"], "skill.ai", evidence_=[ev])], snapshot_id="cap_other")
        evaluation = evaluation_from_dict(doc)
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, dataset, taxonomy)

    def test_taxonomy_version_mismatch_rejected(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        doc = make_evaluation(
            [label(rec["source_id"], "skill.ai", evidence_=[ev])],
            taxonomy_version="technical-skills-9.9.9",
        )
        evaluation = evaluation_from_dict(doc)
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, dataset, taxonomy)

    def test_dataset_type_mismatch_rejected(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        doc = make_evaluation([label(rec["source_id"], "skill.ai", evidence_=[ev])], dataset_type="full_feed")
        evaluation = evaluation_from_dict(doc)
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, dataset, taxonomy)

    def test_sample_shape_mismatch_rejected(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        ev = evidence(rec, "title_raw", rec["title_raw"])
        doc = make_evaluation(
            [label(rec["source_id"], "skill.ai", evidence_=[ev])],
            sample={"records": 19, "page": 1, "limit": 20, "offset": 0, "complete": False},
        )
        evaluation = evaluation_from_dict(doc)
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, dataset, taxonomy)

    def test_evidence_offsets_and_quotes_validated_exactly(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        value = rec["title_raw"]
        span = resolve_quote_span(value, rec["title_raw"])
        assert span is not None
        start, end = span
        assert value[start:end] == rec["title_raw"]
        base = {"field": "title_raw", "exact_quote": rec["title_raw"], "char_start": start, "char_end": end}
        for mutated in (
            {**base, "char_start": start + 1},
            {**base, "char_end": end - 1},
            {**base, "exact_quote": "German Audio Recorder"},
            {**base, "char_end": len(value) + 5},
        ):
            doc = make_evaluation([label(rec["source_id"], "skill.ai", evidence_=[mutated])])
            evaluation = evaluation_from_dict(doc)
            with pytest.raises(EvaluationError):
                validate_evaluation(evaluation, dataset, taxonomy)

    def test_evidence_field_must_be_existing_string_field(self, dataset, taxonomy) -> None:
        rec = dataset["records"][0]
        bad = {"field": "categories_raw", "exact_quote": "x", "char_start": 0, "char_end": 1}
        doc = make_evaluation([label(rec["source_id"], "skill.ai", evidence_=[bad])])
        with pytest.raises(EvaluationError):
            evaluation_from_dict(doc)
        missing = {"field": "excerpt_raw", "exact_quote": "x", "char_start": 0, "char_end": 1}
        rec_no_excerpt = {**rec, "excerpt_raw": None}
        docs = make_dataset([rec_no_excerpt])
        evaluation = evaluation_from_dict(
            make_evaluation(
                [label(rec["source_id"], "skill.ai", evidence_=[missing])],
                sample_records=1,
            )
        )
        with pytest.raises(EvaluationError):
            validate_evaluation(evaluation, docs, taxonomy)

    def test_committed_artifact_validates_against_dataset(self, evaluation, dataset, taxonomy) -> None:
        validate_evaluation(evaluation, dataset, taxonomy)  # no debe lanzar excepción


class TestPredictions:
    def test_predictions_dedup_per_record(self, dataset) -> None:
        record = make_record("rec-1", skills=["skill.a", "skill.a", "skill.b"])
        preds = predictions_by_record(make_dataset([record]))
        assert preds == {"rec-1": ("skill.a", "skill.b")}

    def test_committed_predictions(self, dataset) -> None:
        preds = predictions_by_record(dataset)
        assert len(preds) == 20
        assert sum(len(skills) for skills in preds.values()) == EXPECTED["predicted_pairs"]


# ---------------------------------------------------------------------------
# Contingencia: TP/FP/FN/TN exactos y reglas de exclusión.
# ---------------------------------------------------------------------------


class TestContingency:
    def test_exact_tp_fp_fn_tn(self, evaluation, dataset) -> None:
        cont = build_contingency(evaluation, dataset)
        assert cont["tp"] == EXPECTED["tp"]
        assert cont["fp"] == EXPECTED["fp"]
        assert cont["fn"] == EXPECTED["fn"]
        assert cont["tn"] == EXPECTED["tn"]
        assert cont["uncertain"] == EXPECTED["uncertain"]
        assert cont["labeled_pairs"] == EXPECTED["labels_total"]
        assert cont["non_uncertain_labeled_pairs"] == EXPECTED["non_uncertain"]

    def test_uncertain_labels_excluded_from_contingency(self, evaluation, dataset) -> None:
        cont = build_contingency(evaluation, dataset)
        # Las cuatro celdas de contingencia juntas cubren exactamente los pares
        # etiquetados no inciertos; los pares inciertos no aparecen en ninguna celda.
        assert cont["tp"] + cont["fp"] + cont["fn"] + cont["tn"] == EXPECTED["non_uncertain"]
        assert all(entry["label"] != "uncertain" for entry in cont["false_positives"])
        assert all(entry["label"] != "uncertain" for entry in cont["false_negatives"])

    def test_unlabeled_pairs_excluded_not_negatives(self, evaluation, dataset) -> None:
        cont = build_contingency(evaluation, dataset)
        # skill.data_science se predice para el registro engineering-data-tools pero
        # NO tiene etiqueta: no debe aparecer como FP ni inflar ningún conteo.
        assert cont["unlabeled_predicted_pairs"] == EXPECTED["unlabeled_predicted_pairs"]
        fp_keys = {(entry["source_id"], entry["skill_id"]) for entry in cont["false_positives"]}
        s1 = dataset["records"][1]["source_id"]
        italian = dataset["records"][2]["source_id"]
        unlabeled_ai = dataset["records"][4]["source_id"]  # portuguese-portugal: predicted ai, no label
        assert (s1, "skill.data_science") not in fp_keys
        assert (unlabeled_ai, "skill.ai") not in fp_keys  # predicho pero sin etiquetar -> excluido
        assert (italian, "skill.ai") in fp_keys  # etiquetado not_supported + predicho -> FP real

    def test_false_positive_entries_carry_matcher_evidence(self, evaluation, dataset) -> None:
        cont = build_contingency(evaluation, dataset)
        assert len(cont["false_positives"]) == EXPECTED["fp"]
        first = cont["false_positives"][0]
        assert first["label"] == "not_supported"
        me = first["matcher_evidence"]
        assert me["field"] in EVIDENCE_FIELDS
        assert isinstance(me["matched_term"], str) and me["matched_term"]
        assert me["term_type"] in ("keyword", "alias")
        assert isinstance(me["excerpt"], str) and me["excerpt"]
        # La predicción de ai para el rol de audio alemán coincide en el campo de descripción.
        german = dataset["records"][0]["source_id"]
        for entry in cont["false_positives"]:
            if entry["source_id"] == german and entry["skill_id"] == "skill.ai":
                assert entry["matcher_evidence"]["field"] == "description_html_raw"
                assert entry["matcher_evidence"]["matched_term"] == "ai"
                assert "next-generation AI systems" in entry["matcher_evidence"]["excerpt"]

    def test_false_negative_entries_carry_gold_evidence(self, evaluation, dataset) -> None:
        cont = build_contingency(evaluation, dataset)
        assert len(cont["false_negatives"]) == EXPECTED["fn"]
        for entry in cont["false_negatives"]:
            assert entry["label"] == "supported"
            assert entry["gold_evidence"]
            for ev in entry["gold_evidence"]:
                assert ev["field"] in EVIDENCE_FIELDS
                assert ev["exact_quote"]

    def test_per_skill_breakdown(self, evaluation, dataset) -> None:
        cont = build_contingency(evaluation, dataset)
        assert cont["per_skill"]["skill.ai"] == {"tp": 3, "fp": 5, "fn": 0, "tn": 1}
        assert cont["per_skill"]["skill.git"] == {"tp": 0, "fp": 0, "fn": 0, "tn": 4}
        assert cont["per_skill"]["skill.python"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 1}
        assert sorted(cont["per_skill"]) == sorted(cont["per_skill"])

    def test_predicted_skill_counts_at_most_once_per_record(self, dataset) -> None:
        record = make_record(
            "rec-dup", skills=["skill.a", "skill.a"], title="Python Python Python", description="<p>a b</p>"
        )
        ds = make_dataset([record])
        eval_doc = evaluation_from_dict(
            make_evaluation(
                [label("rec-dup", "skill.a", evidence_=[evidence(record, "title_raw", "Python")])],
                sample_records=1,
            )
        )
        validate_evaluation(eval_doc, ds, taxonomy_from_dict(make_taxonomy_doc()))
        cont = build_contingency(eval_doc, ds)
        assert cont["tp"] == 1  # la predicción duplicada cuenta una vez

    def test_synthetic_exact_arithmetic(self) -> None:
        # Dos registros, tres habilidades; un subconjunto etiquetado artesanal con una mezcla de
        # TP/FP/FN/TN/inciertos.
        taxonomy = taxonomy_from_dict(make_taxonomy_doc())
        r1 = make_record("rec-1", skills=["skill.a", "skill.c"], title="alpha beta")
        r2 = make_record("rec-2", skills=["skill.b"], title="gamma")
        ds = make_dataset([r1, r2])
        # rec-1 predice a y c; rec-2 predice b. Subconjunto etiquetado: a sup (TP),
        # b ns (FP), c uncertain; rec-2 a ns (TN), c ns (TN).
        labels = [
            label("rec-1", "skill.a", evidence_=[evidence(r1, "title_raw", "alpha")]),
            label("rec-1", "skill.b", value="not_supported"),
            label("rec-1", "skill.c", value="uncertain", evidence_=[evidence(r1, "title_raw", "beta")]),
            label("rec-2", "skill.a", value="not_supported"),
            label("rec-2", "skill.b", value="not_supported"),
            label("rec-2", "skill.c", value="not_supported"),
        ]
        evaluation = evaluation_from_dict(make_evaluation(labels, sample_records=2))
        validate_evaluation(evaluation, ds, taxonomy)
        cont = build_contingency(evaluation, ds)
        assert cont["tp"] == 1  # rec-1 a
        assert cont["fp"] == 1  # rec-2 b predicho pero etiquetado not_supported
        assert cont["fn"] == 0
        assert cont["tn"] == 3  # rec-1 b, rec-2 a, rec-2 c
        assert cont["uncertain"] == 1
        # rec-1 skill.c está etiquetada como uncertain (sigue siendo una etiqueta); todos los
        # demás pares predichos también están etiquetados, así que nada queda sin etiquetar.
        assert cont["unlabeled_predicted_pairs"] == 0


# ---------------------------------------------------------------------------
# Métricas: precisión/recall/F1, micro, macro, denominadores cero.
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_primary_precision_recall_f1_exact(self, evaluation, dataset, taxonomy) -> None:
        metrics = compute_metrics(evaluation, dataset, taxonomy)
        primary = metrics["primary"]
        assert primary["tp"] == EXPECTED["tp"]
        assert primary["fp"] == EXPECTED["fp"]
        assert primary["fn"] == EXPECTED["fn"]
        assert primary["tn"] == EXPECTED["tn"]
        assert primary["precision"] == pytest.approx(EXPECTED["precision"])
        assert primary["recall"] == pytest.approx(EXPECTED["recall"])
        assert primary["f1"] == pytest.approx(EXPECTED["f1"])
        assert primary["denominators"] == {"tp_fp": 43, "tp_fn": 38}

    def test_micro_metrics_over_all_non_uncertain_pairs(self, evaluation, dataset, taxonomy) -> None:
        metrics = compute_metrics(evaluation, dataset, taxonomy)
        micro = metrics["micro"]
        assert micro["precision"] == pytest.approx(EXPECTED["precision"])
        assert micro["recall"] == pytest.approx(EXPECTED["recall"])
        assert micro["f1"] == pytest.approx(EXPECTED["f1"])
        assert "non-uncertain" in micro["scope_note"]
        assert micro["denominator_pairs"] == EXPECTED["non_uncertain"]

    def test_macro_metrics_explicit_scope(self, evaluation, dataset, taxonomy) -> None:
        metrics = compute_metrics(evaluation, dataset, taxonomy)
        macro = metrics["macro"]
        assert len(macro["skills_in_scope"]) == 35
        assert macro["skills_excluded_undefined"] == ["skill.git", "skill.java"]
        assert "per-skill" in macro["scope_note"]
        assert macro["precision"] == pytest.approx(EXPECTED["macro_precision"])
        assert macro["recall"] == pytest.approx(EXPECTED["macro_recall"])
        assert macro["f1"] == pytest.approx(EXPECTED["macro_f1"])
        assert macro["per_skill"]["skill.ai"] == {
            "tp": 3,
            "fp": 5,
            "fn": 0,
            "tn": 1,
            "precision": pytest.approx(0.375),
            "recall": 1.0,
            "f1": pytest.approx(6 / 11),
        }

    def test_uncertain_reported_separately(self, evaluation, dataset, taxonomy) -> None:
        metrics = compute_metrics(evaluation, dataset, taxonomy)
        assert metrics["uncertain"]["count"] == EXPECTED["uncertain"]
        assert "excluded" in metrics["uncertain"]["excluded_note"]

    def test_zero_denominator_safety_all_tn(self) -> None:
        taxonomy = taxonomy_from_dict(make_taxonomy_doc())
        r1 = make_record("rec-1", skills=())
        ds = make_dataset([r1])
        labels = [label("rec-1", "skill.a", value="not_supported")]
        evaluation = evaluation_from_dict(make_evaluation(labels, sample_records=1))
        validate_evaluation(evaluation, ds, taxonomy)
        metrics = compute_metrics(evaluation, ds, taxonomy)
        primary = metrics["primary"]
        assert primary["tp"] == 0 and primary["fp"] == 0 and primary["fn"] == 0 and primary["tn"] == 1
        assert primary["precision"] is None
        assert primary["recall"] is None
        assert primary["f1"] is None
        assert "undefined" in primary["note"]
        assert metrics["macro"]["precision"] is None
        assert metrics["macro"]["recall"] is None
        assert metrics["macro"]["f1"] is None

    def test_zero_denominator_safety_tp_zero_fn_positive(self) -> None:
        taxonomy = taxonomy_from_dict(make_taxonomy_doc())
        r1 = make_record("rec-1", skills=(), title="Python everywhere")
        ds = make_dataset([r1])
        labels = [label("rec-1", "skill.a", evidence_=[evidence(r1, "title_raw", "Python")])]
        evaluation = evaluation_from_dict(make_evaluation(labels, sample_records=1))
        validate_evaluation(evaluation, ds, taxonomy)
        metrics = compute_metrics(evaluation, ds, taxonomy)
        primary = metrics["primary"]
        assert primary["tp"] == 0 and primary["fp"] == 0 and primary["fn"] == 1 and primary["tn"] == 0
        assert primary["precision"] is None
        assert primary["recall"] == 0.0
        assert primary["f1"] == 0.0

    def test_zero_denominator_safety_tp_zero_fp_positive(self) -> None:
        taxonomy = taxonomy_from_dict(make_taxonomy_doc())
        r1 = make_record("rec-1", skills=["skill.a"])
        ds = make_dataset([r1])
        labels = [label("rec-1", "skill.a", value="not_supported")]
        evaluation = evaluation_from_dict(make_evaluation(labels, sample_records=1))
        validate_evaluation(evaluation, ds, taxonomy)
        metrics = compute_metrics(evaluation, ds, taxonomy)
        primary = metrics["primary"]
        assert primary["tp"] == 0 and primary["fp"] == 1 and primary["fn"] == 0 and primary["tn"] == 0
        assert primary["precision"] == 0.0
        assert primary["recall"] is None
        assert primary["f1"] == 0.0

    def test_empty_predictions_set(self) -> None:
        taxonomy = taxonomy_from_dict(make_taxonomy_doc())
        r1 = make_record("rec-1", skills=(), title="no skills here")
        r2 = make_record("rec-2", skills=(), title="nothing either")
        ds = make_dataset([r1, r2])
        labels = [
            label("rec-1", "skill.a", evidence_=[evidence(r1, "title_raw", "no skills")]),
            label("rec-2", "skill.b", value="not_supported"),
        ]
        evaluation = evaluation_from_dict(make_evaluation(labels, sample_records=2))
        validate_evaluation(evaluation, ds, taxonomy)
        cont = build_contingency(evaluation, ds)
        assert cont["tp"] == 0 and cont["fp"] == 0 and cont["fn"] == 1 and cont["tn"] == 1
        metrics = compute_metrics(evaluation, ds, taxonomy)
        assert metrics["primary"]["precision"] is None
        assert metrics["primary"]["recall"] == 0.0
        assert metrics["primary"]["f1"] == 0.0


# ---------------------------------------------------------------------------
# Cobertura, informe, determinismo y materialización.
# ---------------------------------------------------------------------------


class TestCoverageAndReport:
    def test_coverage_numbers(self, evaluation, dataset, taxonomy) -> None:
        report = build_report(evaluation, dataset, taxonomy)
        coverage = report["coverage"]
        assert coverage["labeled_pairs"] == EXPECTED["labels_total"]
        assert coverage["non_uncertain_labeled_pairs"] == EXPECTED["non_uncertain"]
        assert coverage["total_pairs"] == EXPECTED["total_pairs"]
        assert coverage["annotated_records"] == EXPECTED["annotated_records"]
        assert len(coverage["annotated_record_ids"]) == EXPECTED["annotated_records"]
        assert coverage["pair_coverage"] == pytest.approx(60 / 740)
        assert coverage["non_uncertain_pair_coverage"] == pytest.approx(56 / 740)
        assert coverage["annotated_record_coverage"] == pytest.approx(11 / 20)

    def test_label_distribution(self, evaluation, dataset, taxonomy) -> None:
        report = build_report(evaluation, dataset, taxonomy)
        dist = report["label_distribution"]
        assert dist["supported"] == EXPECTED["tp"]
        assert dist["not_supported"] == EXPECTED["fp"] + EXPECTED["tn"]
        assert dist["uncertain"] == EXPECTED["uncertain"]
        assert dist["total"] == EXPECTED["labels_total"]

    def test_record_summary_from_dataset(self, evaluation, dataset, taxonomy) -> None:
        report = build_report(evaluation, dataset, taxonomy)
        summary = report["record_summary"]
        assert summary["record_count"] == 20
        assert summary["records_with_evidence"] == 20
        assert summary["records_without_evidence"] == 0
        assert summary["no_evidence_record_ids"] == []

    def test_report_sections_and_guardrails(self, evaluation, dataset, taxonomy) -> None:
        report = build_report(evaluation, dataset, taxonomy)
        assert report["evaluation_status"] == EVALUATION_STATUS
        assert report["snapshot_id"] == SNAPSHOT_ID
        assert report["taxonomy_version"] == "technical-skills-0.1.0"
        assert report["attribution_url"] == "https://himalayas.app"
        assert report["metrics"]["primary"]["tp"] == EXPECTED["tp"]
        assert report["metrics"]["primary"]["fp"] == EXPECTED["fp"]
        assert report["metrics"]["primary"]["fn"] == EXPECTED["fn"]
        assert report["metrics"]["primary"]["tn"] == EXPECTED["tn"]
        assert len(report["false_positives"]) == EXPECTED["fp"]
        assert len(report["false_negatives"]) == EXPECTED["fn"]
        assert any("draft" in w for w in report["warnings"])
        assert any("market" in limitation for limitation in report["limitations"])
        assert any("unlabeled" in g for g in report["guardrails"])
        assert any("uncertain" in g for g in report["guardrails"])

    def test_report_deterministic_repeated_output(self, evaluation, dataset, taxonomy) -> None:
        first = build_report(evaluation, dataset, taxonomy)
        second = build_report(evaluation, dataset, taxonomy)
        assert first == second
        assert serialize_report(first) == serialize_report(second)
        assert serialize_report(first) == serialize_report(json.loads(serialize_report(first).decode("utf-8")))

    def test_evaluation_serialization_deterministic(self, evaluation, dataset, taxonomy) -> None:
        doc = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
        canonical = json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        assert EVALUATION_PATH.read_text(encoding="utf-8") == canonical
        assert serialize_evaluation(doc) == canonical.encode("utf-8")

    def test_no_full_raw_descriptions_in_artifacts(self, evaluation, dataset, taxonomy) -> None:
        doc = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
        report = build_report(evaluation, dataset, taxonomy)

        # Fragmentos que aparecen en las descripciones crudas y nunca deben filtrarse
        # a ninguno de los artefactos (solo se permiten citas/extractos cortos).
        banned = ("micro1 is engaging", "Originally posted on", "Scope of Work", "<p>", "<h3>", "Role Title:")

        def walk(node):
            if isinstance(node, dict):
                assert "description_html_raw" not in node, "la clave de descripción cruda se filtró"
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
        # Las citas de evidencia y los extractos del matcher son cortos (nunca descripciones completas).
        for entry in evaluation.labels:
            for ev in entry.evidence:
                assert len(ev.exact_quote) <= 100
        for fp in report["false_positives"]:
            assert len(fp["matcher_evidence"]["excerpt"]) <= 200
        for fn in report["false_negatives"]:
            for ev in fn["gold_evidence"]:
                assert len(ev["exact_quote"]) <= 100

    def test_resolve_quote_span_helper(self) -> None:
        assert resolve_quote_span("python python3", "python") == (0, 6)
        assert resolve_quote_span("python python3", "python3") == (7, 14)
        assert resolve_quote_span("a b c", "nope") is None
        assert resolve_quote_span("", "x") is None
        assert resolve_quote_span("abc", "abc") == (0, 3)


class TestMaterializeReport:
    def test_materialize_report_writes_and_is_idempotent(self, tmp_path) -> None:
        output = tmp_path / "report.json"
        first = materialize_evaluation_report(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            evaluation_path=EVALUATION_PATH,
            report_output_path=output,
        )
        assert first == output
        assert output.exists()
        dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        taxonomy = load_taxonomy(TAXONOMY_PATH)
        evaluation = load_evaluation(EVALUATION_PATH)
        expected = serialize_report(build_report(evaluation, dataset, taxonomy))
        assert output.read_bytes() == expected
        # Re-ejecutar es un no-op a nivel de bytes.
        again = materialize_evaluation_report(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            evaluation_path=EVALUATION_PATH,
            report_output_path=output,
        )
        assert again == output
        assert output.read_bytes() == expected

    def test_materialize_refuses_overwrite_with_different_content(self, tmp_path) -> None:
        output = tmp_path / "report.json"
        output.write_text('{"stale": true}', encoding="utf-8")
        with pytest.raises(DatasetError):
            materialize_evaluation_report(
                dataset_path=DATASET_PATH,
                taxonomy_path=TAXONOMY_PATH,
                evaluation_path=EVALUATION_PATH,
                report_output_path=output,
            )

    def test_materialize_rejects_invalid_labels_without_writing(self, tmp_path) -> None:
        doc = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
        doc["labels"][0]["evidence"][0]["char_start"] = 0  # corrompe el primer tramo de cita
        bad_eval = tmp_path / "bad-eval.json"
        bad_eval.write_text(json.dumps(doc), encoding="utf-8")
        output = tmp_path / "report.json"
        with pytest.raises(EvaluationError):
            materialize_evaluation_report(
                dataset_path=DATASET_PATH,
                taxonomy_path=TAXONOMY_PATH,
                evaluation_path=bad_eval,
                report_output_path=output,
            )
        assert not output.exists()

    def test_materialize_rejects_noncanonical_evaluation_artifact(self, tmp_path) -> None:
        text = EVALUATION_PATH.read_text(encoding="utf-8")
        noncanonical = tmp_path / "noncanonical.json"
        noncanonical.write_text(text.rstrip("\n") + "  ", encoding="utf-8")  # espacio en blanco final
        output = tmp_path / "report.json"
        with pytest.raises(EvaluationError):
            materialize_evaluation_report(
                dataset_path=DATASET_PATH,
                taxonomy_path=TAXONOMY_PATH,
                evaluation_path=noncanonical,
                report_output_path=output,
            )
        assert not output.exists()
