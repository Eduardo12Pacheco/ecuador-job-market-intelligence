"""Comando offline: materializa la revisión final adjudicada por humanos (v0.3.0).

``materialize_final_review`` lee el artefacto de revisión de segunda pasada
v0.2.0 CONGELADO (``data/evaluation/skill-extraction-review-0.2.0.json``), su informe
(``data/evaluation/skill-extraction-review-report-0.2.0.json``) y el conjunto de
datos analítico local (``data/analytics/development-sample-0.1.0.json``). Aplica
exactamente las siete decisiones humanas aprobadas (HR-01…HR-07) como un registro
de adjudicación separado, conserva sin cambios todas las demás etiquetas, recalcula
la distribución de etiquetas, la contingencia a nivel de par contra las predicciones
embebidas de la línea base de palabras clave del conjunto de datos y las métricas
micro/macro a partir de las 740 etiquetas resultantes, y escribe los dos artefactos
deterministas:

    data/evaluation/skill-extraction-review-0.3.0.json
    data/evaluation/skill-extraction-review-report-0.3.0.json

Ambos artefactos declaran ``annotation_status: human_review_complete``,
``human_review_required: false`` y ``human_review_complete: true``: la evaluación
es FINAL SOLO PARA ESTA MUESTRA CURADA DE 20 OFERTAS — su alcance se limita a esta
muestra curada y no puede generalizarse al mercado completo. La etiqueta original
de la segunda pasada, la evidencia, las citas/offsets exactos, la razón, la
pregunta, las notas y los ids de fuente se conservan para cada par; los siete
pares adjudicados llevan además un ``final_label`` y un ``adjudication_id`` que
enlaza con el libro ``human_review_decisions`` auditable. El registro histórico
v0.2.0 (distribución de etiquetas, métricas, comparación primera-vs-segunda y la
cola de revisión humana de 7 ítems) se conserva bajo el bloque ``historical`` del
informe; la redacción del alcance histórico se normaliza a ``reference label``
mientras el artefacto fuente v0.2.0 permanece intacto. La ``human_review_queue``
actual es ``count: 0, items: []``.

La generación es determinista y de cierre ante fallos: los artefactos de entrada
deben estar serializados canónicamente, cada decisión debe resolverse al par
congelado v0.2.0 para el que fue aprobada, cada cita/offset de evidencia debe
re-verificarse contra el conjunto de datos y un artefacto de salida existente con
contenido diferente se rechaza (nunca se sobrescribe). No se consultan páginas
crudas, manifiestos, respuestas de API ni red, y no se lee ningún reloj de pared:
la fecha de aprobación es la fecha fija del repositorio ``2026-08-02``.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import DatasetError, EvaluationError
from .evaluate import _write_atomic
from .evaluation import (
    _matcher_evidence,
    _precision_recall_f1,
    predictions_by_record,
)

#: Versión del artefacto de revisión final adjudicada por humanos.
FINAL_VERSION = "skill-extraction-review-0.3.0"

#: El discriminador de tipo del artefacto (mismo tipo que la revisión de segunda pasada).
FINAL_KIND = "skill_extraction_review"

#: El único estado permitido: revisión humana completa, final para la muestra curada.
FINAL_STATUS = "human_review_complete"

#: Fecha de aprobación fija del repositorio (nunca leída del reloj de pared).
APPROVAL_DATE = "2026-08-02"

#: Fuente de aprobación registrada para cada decisión.
APPROVAL_SOURCE = "explicit project-owner instruction"

#: Rutas por defecto, relativas a la raíz del repositorio.
REVIEW_ARTIFACT_DEFAULT_PATH = "data/evaluation/skill-extraction-review-0.2.0.json"
REVIEW_REPORT_DEFAULT_PATH = "data/evaluation/skill-extraction-review-report-0.2.0.json"
DATASET_DEFAULT_PATH = "data/analytics/development-sample-0.1.0.json"
FINAL_ARTIFACT_DEFAULT_PATH = "data/evaluation/skill-extraction-review-0.3.0.json"
FINAL_REPORT_DEFAULT_PATH = "data/evaluation/skill-extraction-review-report-0.3.0.json"

#: Enumerado de etiquetas cerrado de los artefactos de anotación.
LABEL_VALUES = frozenset({"supported", "not_supported", "uncertain"})

# ---------------------------------------------------------------------------
# Las siete decisiones humanas aprobadas (HR-01…HR-07).
#
# Cada entrada mapea el par congelado (source_id, skill_id) a su etiqueta final.
# ``expected_second_pass_label`` protege contra la deriva: la decisión solo aplica
# cuando el artefacto congelado v0.2.0 todavía lleva la etiqueta original exacta de
# la segunda pasada para la que fue aprobada. ``criterion`` es la razón de decisión
# exacta aprobada por el dueño del proyecto; la razón original por etiqueta se
# conserva intacta.
# ---------------------------------------------------------------------------

HUMAN_DECISIONS: tuple[dict[str, Any], ...] = (
    {
        "item_id": "HR-01",
        "source_id": "https://himalayas.app/companies/bjak/jobs/strategy-operations-associate-7652220692",
        "skill_id": "skill.ai",
        "expected_second_pass_label": "uncertain",
        "final_label": "not_supported",
        "criterion": ("AI only company/product context, role does not require or perform AI work."),
    },
    {
        "item_id": "HR-02",
        "source_id": "https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist",
        "skill_id": "skill.ai",
        "expected_second_pass_label": "not_supported",
        "final_label": "not_supported",
        "criterion": ("posting says no prior AI experience required and AI is project context, not role tasks."),
    },
    {
        "item_id": "HR-03",
        "source_id": "https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist",
        "skill_id": "skill.data_science",
        "expected_second_pass_label": "uncertain",
        "final_label": "not_supported",
        "criterion": (
            "data science is only a possible university degree field, not evidence the role executes data-science work."
        ),
    },
    {
        "item_id": "HR-04",
        "source_id": "https://himalayas.app/companies/micro1/jobs/german-audio-recording-expert",
        "skill_id": "skill.machine_learning",
        "expected_second_pass_label": "uncertain",
        "final_label": "not_supported",
        "criterion": ("recordings are later used by ML applications, but role does not develop/apply ML."),
    },
    {
        "item_id": "HR-05",
        "source_id": "https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert",
        "skill_id": "skill.ai",
        "expected_second_pass_label": "uncertain",
        "final_label": "supported",
        "criterion": (
            "explicit experience in AI data collection is a role-related "
            "nice-to-have; optional does not mean nonexistent."
        ),
    },
    {
        "item_id": "HR-06",
        "source_id": "https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert",
        "skill_id": "skill.machine_learning",
        "expected_second_pass_label": "not_supported",
        "final_label": "not_supported",
        "criterion": ("AI models/training are mentioned, but no explicit ML work; AI and ML are not interchangeable."),
    },
    {
        "item_id": "HR-07",
        "source_id": "https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-brazil",
        "skill_id": "skill.ai",
        "expected_second_pass_label": "uncertain",
        "final_label": "supported",
        "criterion": (
            "producing audio samples for AI training relates directly to the role; "
            "the AI-Specialist category reinforces but is not the sole basis."
        ),
    },
)

_DECISION_BY_PAIR = {(d["source_id"], d["skill_id"]): d for d in HUMAN_DECISIONS}

# Justificación exacta provista con las decisiones humanas aprobadas, conservada
# en el libro junto al criterio normalizado que usa el materializador.
DECISION_REASON_ES = {
    "HR-01": (
        "La IA aparece únicamente como contexto del producto de la empresa; el cargo no exige ni ejecuta trabajo de IA."
    ),
    "HR-02": (
        "La oferta indica que no requiere experiencia previa en IA y la mención de IA "
        "pertenece al contexto del proyecto, no a las tareas del cargo."
    ),
    "HR-03": (
        "data science aparece únicamente como campo posible de título universitario; "
        "no demuestra que el cargo ejecute tareas de Data Science."
    ),
    "HR-04": (
        "Las grabaciones serán usadas posteriormente por aplicaciones de Machine Learning, "
        "pero el cargo no desarrolla ni aplica Machine Learning."
    ),
    "HR-05": (
        "La oferta menciona explícitamente experiencia en recolección de datos para IA "
        "como una ventaja relacionada con el rol. Que sea opcional no significa que la "
        "actividad no exista."
    ),
    "HR-06": (
        "Se mencionan AI models y AI training, pero no existe evidencia explícita de "
        "trabajo de Machine Learning. IA y Machine Learning no deben tratarse como "
        "etiquetas intercambiables."
    ),
    "HR-07": (
        "La producción de muestras de audio para entrenamiento de IA está relacionada "
        "directamente con el rol. La categoría AI-Specialist solo refuerza la evidencia; "
        "no debe ser la única base de la decisión."
    ),
}

FINAL_ANNOTATION_METHOD = (
    "Human-adjudicated final review: the frozen v0.2.0 draft second pass "
    "(skill-extraction-review-0.2.0, annotation_status: draft_second_pass, "
    "human_review_required: true) labeled all 740 (source_id, skill_id) pairs of the "
    "development analytics dataset. The seven queued decisions (HR-01..HR-07) were "
    "approved on 2026-08-02 by explicit project-owner instruction; each decision "
    "applies exactly one final label to its frozen pair and preserves the original "
    "second-pass label, evidence, exact quotes and half-open offsets, reason, "
    "question, notes, and source ids. All other labels are unchanged. The "
    "final_label of every pair is the label of record: counts, the pair-level "
    "contingency against the dataset's embedded keyword-baseline predictions "
    "(skill_evidence.skills), and the micro/macro metrics are recomputed from the "
    "resulting 740 labels. The evaluation is FINAL FOR THIS CURATED 20-OFFER SAMPLE "
    "ONLY (annotation_status: human_review_complete, human_review_required: false); "
    "its scope is limited to this curated sample and does not generalize to the full market. No "
    "matcher or taxonomy rule was changed."
)


def _read_json(path: str | Path, error_type: type[Exception], label: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise error_type(f"no se puede leer {label} {path}: {exc}") from exc
    except ValueError as exc:
        raise error_type(f"{label} {path} no es JSON válido: {exc}") from exc


def _serialize(doc: Mapping[str, Any]) -> bytes:
    """Serialización JSON canónica en UTF-8 (claves ordenadas, sangría de 2 espacios)."""
    return (json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _check_canonical(path: Path, doc: Mapping[str, Any], label: str) -> None:
    raw_text = path.read_text(encoding="utf-8")
    if raw_text != _serialize(doc).decode("utf-8"):
        raise EvaluationError(
            f"{label} {path} no está serializado canónicamente; el artefacto congelado debe "
            f"ser reproducible (claves ordenadas, sangría de 2 espacios, salto de línea final)"
        )


def _verify_evidence_quotes(labels: list[dict], record_by_source: Mapping[str, Any]) -> None:
    """Re-verifica cada cita/offset de evidencia conservado contra el conjunto de datos (cierre ante fallos)."""
    for entry in labels:
        record = record_by_source.get(entry["source_id"], {})
        for ev in entry.get("evidence", []):
            value = record.get(ev.get("field", ""))
            quote = ev.get("exact_quote", "")
            start = ev.get("char_start")
            end = ev.get("char_end")
            if not isinstance(value, str) or not isinstance(start, int) or not isinstance(end, int):
                raise EvaluationError(
                    f"la evidencia de ({entry['source_id']}, {entry['skill_id']}) no puede "
                    f"re-verificarse: el campo {ev.get('field')!r} no es una cadena o faltan los offsets"
                )
            if start < 0 or end < start or end > len(value) or value[start:end] != quote:
                raise EvaluationError(
                    f"la cita de evidencia de ({entry['source_id']}, {entry['skill_id']}) ya no "
                    f"coincide con el conjunto de datos: {quote!r} != value[{start}:{end}]"
                )


def _apply_decisions(labels: list[dict]) -> list[dict]:
    """Devuelve las 740 etiquetas finales: los siete mapeos aplicados, todo lo demás sin cambios.

    Cada etiqueta conserva sus campos originales y gana ``final_label`` (la etiqueta de
    registro); los siete pares adjudicados ganan además ``adjudication_id``.
    """
    final_labels: list[dict] = []
    used: set[str] = set()
    for entry in labels:
        decision = _DECISION_BY_PAIR.get((entry.get("source_id"), entry.get("skill_id")))
        final: dict[str, Any] = dict(entry)
        if decision is None:
            final["final_label"] = entry["label"]
        else:
            if decision["expected_second_pass_label"] != entry["label"]:
                raise EvaluationError(
                    f"{decision['item_id']} espera la etiqueta de segunda pasada "
                    f"{decision['expected_second_pass_label']!r} para "
                    f"({entry['source_id']}, {entry['skill_id']}) pero el artefacto congelado "
                    f"lleva {entry['label']!r}; la decisión no aplica a este par"
                )
            if decision["final_label"] not in LABEL_VALUES:
                raise EvaluationError(
                    f"la etiqueta final {decision['final_label']!r} de {decision['item_id']} "
                    f"no es uno de {LABEL_VALUES}"
                )
            final["final_label"] = decision["final_label"]
            final["adjudication_id"] = decision["item_id"]
            used.add(decision["item_id"])
        final_labels.append(final)
    missing = [d["item_id"] for d in HUMAN_DECISIONS if d["item_id"] not in used]
    if missing:
        raise EvaluationError(f"las decisiones humanas no se aplicaron a las etiquetas congeladas: {sorted(missing)}")
    return final_labels


def _build_decision_ledger(
    labels: list[dict],
    historical_queue_items: list[dict],
) -> list[dict]:
    """Libro auditable: una entrada por decisión aprobada, con todas las entradas conservadas."""
    first_pass_by_pair = {(item.get("source_id"), item.get("skill_id")): item for item in historical_queue_items}
    ledger: list[dict] = []
    for decision in HUMAN_DECISIONS:
        pair = (decision["source_id"], decision["skill_id"])
        label = next(entry for entry in labels if entry["source_id"] == pair[0] and entry["skill_id"] == pair[1])
        queue_item = first_pass_by_pair.get(pair, {})
        first_pass_label = queue_item.get("first_draft_label")
        ledger.append(
            {
                "item_id": decision["item_id"],
                "source_id": decision["source_id"],
                "skill_id": decision["skill_id"],
                "first_pass_label": first_pass_label,
                "first_pass_unlabeled": first_pass_label is None,
                "second_pass_label": label["label"],
                "final_label": decision["final_label"],
                "approval_date": APPROVAL_DATE,
                "approval_source": APPROVAL_SOURCE,
                "criterion": decision["criterion"],
                "decision_reason": DECISION_REASON_ES[decision["item_id"]],
                "reason": label.get("reason"),
                "question": label.get("human_review_question"),
                "notes": label.get("notes"),
                "evidence": list(label.get("evidence", [])),
            }
        )
    return ledger


def _compute_contingency(final_labels: list[dict], dataset: Mapping[str, Any]) -> dict:
    """Contingencia a nivel de par de las etiquetas finales contra las predicciones del matcher (derivada)."""
    predictions = predictions_by_record(dataset)
    record_by_source = {
        record.get("source_id"): record for record in dataset.get("records", []) if isinstance(record, dict)
    }
    labels_by_pair = {(entry["source_id"], entry["skill_id"]) for entry in final_labels}

    tp = fp = fn = tn = uncertain = 0
    per_skill: dict[str, dict[str, int]] = {}
    false_positives: list[dict] = []
    false_negatives: list[dict] = []

    for entry in final_labels:
        final = entry["final_label"]
        predicted = entry["skill_id"] in predictions.get(entry["source_id"], ())
        if final == "uncertain":
            uncertain += 1
            continue
        if final == "supported":
            if predicted:
                tp += 1
                cell = "tp"
            else:
                fn += 1
                cell = "fn"
                false_negatives.append(
                    {
                        "source_id": entry["source_id"],
                        "skill_id": entry["skill_id"],
                        "label": entry["label"],
                        "final_label": final,
                        "reason": entry.get("reason"),
                        "review_evidence": list(entry.get("evidence", [])),
                    }
                )
        else:  # not_supported
            if predicted:
                fp += 1
                cell = "fp"
                fp_entry: dict[str, Any] = {
                    "source_id": entry["source_id"],
                    "skill_id": entry["skill_id"],
                    "label": entry["label"],
                    "final_label": final,
                    "reason": entry.get("reason"),
                    "matcher_evidence": _matcher_evidence(
                        record_by_source.get(entry["source_id"], {}), entry["skill_id"]
                    ),
                }
                if entry.get("adjudication_id"):
                    fp_entry["adjudication_id"] = entry["adjudication_id"]
                false_positives.append(fp_entry)
            else:
                tn += 1
                cell = "tn"
        counts = per_skill.setdefault(entry["skill_id"], {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        counts[cell] += 1

    unlabeled_predicted_pairs = 0
    for source_id, skills in predictions.items():
        for skill_id in skills:
            if (source_id, skill_id) not in labels_by_pair:
                unlabeled_predicted_pairs += 1

    precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
    scope = sorted(skill_id for skill_id, counts in per_skill.items() if sum(counts.values()) > 0)
    per_skill_metrics: dict[str, dict] = {}
    defined: list[str] = []
    for skill_id in scope:
        counts = per_skill[skill_id]
        p, r, f = _precision_recall_f1(counts["tp"], counts["fp"], counts["fn"])
        per_skill_metrics[skill_id] = {
            "tp": counts["tp"],
            "fp": counts["fp"],
            "fn": counts["fn"],
            "tn": counts["tn"],
            "precision": p,
            "recall": r,
            "f1": f,
        }
        if p is not None or r is not None or f is not None:
            defined.append(skill_id)

    def mean(values: list[float | None]) -> float | None:
        present = [v for v in values if v is not None]
        return sum(present) / len(present) if present else None

    macro = {
        "scope_note": (
            "macro scope: taxonomy skills with at least one non-uncertain final-label pair; "
            "per-skill precision/recall/F1 are computed over that skill's own final labels and "
            "the matcher predictions for the same pairs; skills with no defined value (all "
            "labels not_supported) are excluded and listed explicitly"
        ),
        "precision": mean([per_skill_metrics[s]["precision"] for s in defined]),
        "recall": mean([per_skill_metrics[s]["recall"] for s in defined]),
        "f1": mean([per_skill_metrics[s]["f1"] for s in defined]),
        "skills_in_scope": scope,
        "skills_excluded_undefined": sorted(set(scope) - set(defined)),
        "per_skill": {skill_id: per_skill_metrics[skill_id] for skill_id in scope},
    }
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "uncertain": uncertain,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "unlabeled_predicted_pairs": unlabeled_predicted_pairs,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "macro": macro,
        "record_by_source": record_by_source,
    }


def build_final_doc(
    review_doc: Mapping[str, Any],
    report_doc: Mapping[str, Any],
    dataset: Mapping[str, Any],
) -> dict:
    """Construye el documento determinista del artefacto de revisión v0.3.0."""
    labels = _apply_decisions(list(review_doc.get("labels", [])))
    if len(labels) != 740:
        raise EvaluationError(f"la revisión final debe contener 740 etiquetas; se obtuvieron {len(labels)}")
    _verify_evidence_quotes(
        labels, {record.get("source_id"): record for record in dataset.get("records", []) if isinstance(record, dict)}
    )
    queue = report_doc.get("human_review_queue") or {}
    ledger = _build_decision_ledger(labels, list(queue.get("items", [])))
    return {
        "evaluation_version": FINAL_VERSION,
        "evaluation_kind": FINAL_KIND,
        "annotation_status": FINAL_STATUS,
        "human_review_required": False,
        "human_review_complete": True,
        "approval": {
            "date": APPROVAL_DATE,
            "source": APPROVAL_SOURCE,
            "decisions_count": len(HUMAN_DECISIONS),
        },
        "previous_artifact": {
            "evaluation_version": review_doc.get("evaluation_version"),
            "annotation_status": review_doc.get("annotation_status"),
            "path": "data/evaluation/skill-extraction-review-0.2.0.json",
        },
        "human_review_decisions": ledger,
        "dataset_type": review_doc.get("dataset_type"),
        "dataset_version": review_doc.get("dataset_version"),
        "snapshot_id": review_doc.get("snapshot_id"),
        "taxonomy_version": review_doc.get("taxonomy_version"),
        "matcher_version": review_doc.get("matcher_version"),
        "source": review_doc.get("source"),
        "endpoint": review_doc.get("endpoint"),
        "attribution_url": review_doc.get("attribution_url"),
        "annotation_date": review_doc.get("annotation_date"),
        "annotation_method": FINAL_ANNOTATION_METHOD,
        "sample": dict(review_doc.get("sample", {})),
        "labels": labels,
    }


def build_final_report(
    review_doc: Mapping[str, Any],
    report_doc: Mapping[str, Any],
    dataset: Mapping[str, Any],
    final_doc: Mapping[str, Any],
) -> dict:
    """Construye el documento determinista del informe de revisión v0.3.0."""
    labels = list(final_doc["labels"])
    final_counts = {"supported": 0, "not_supported": 0, "uncertain": 0}
    for entry in labels:
        final_counts[entry["final_label"]] += 1

    cont = _compute_contingency(labels, dataset)
    records = dataset.get("records", [])
    total_pairs = len(records) * len({entry["skill_id"] for entry in labels})
    annotated_ids = sorted({entry["source_id"] for entry in labels})

    report = dataset.get("quality_report") or {}
    coverage = report.get("skill_coverage") or {}
    records_with_evidence = coverage.get("records_with_evidence")
    records_without_evidence = coverage.get("records_without_evidence")
    no_evidence_ids = coverage.get("records_no_evidence")
    if records_with_evidence is None:
        statuses = [
            record.get("skill_evidence", {}).get("evidence_status")
            for record in records
            if isinstance(record.get("skill_evidence"), dict)
        ]
        records_with_evidence = sum(1 for s in statuses if s == "matched")
        records_without_evidence = len(records) - records_with_evidence
        no_evidence_ids = sorted(
            record["source_id"]
            for record in records
            if isinstance(record.get("skill_evidence"), dict)
            and record["skill_evidence"].get("evidence_status") == "no_evidence"
        )

    historical_metrics = dict(report_doc.get("metrics") or {})
    historical_macro = dict(historical_metrics.get("macro") or {})
    historical_scope_note = historical_macro.get("scope_note")
    if isinstance(historical_scope_note, str):
        historical_macro["scope_note"] = historical_scope_note.replace(
            "positive gold or prediction", "positive reference label or prediction"
        )
    if historical_macro:
        historical_metrics["macro"] = historical_macro
    historical = {
        "evaluation_version": report_doc.get("evaluation_version"),
        "report_version": report_doc.get("report_version"),
        "annotation_status": report_doc.get("annotation_status"),
        "label_distribution": report_doc.get("label_distribution"),
        "metrics": historical_metrics,
        "first_vs_second": report_doc.get("first_vs_second"),
        "human_review_queue": report_doc.get("human_review_queue"),
    }
    sample = report_doc.get("sample") or {}
    return {
        "report_version": "0.3.0",
        "evaluation_version": FINAL_VERSION,
        "evaluation_kind": FINAL_KIND,
        "annotation_status": FINAL_STATUS,
        "human_review_required": False,
        "human_review_complete": True,
        "approval": {
            "date": APPROVAL_DATE,
            "source": APPROVAL_SOURCE,
            "decisions_count": len(HUMAN_DECISIONS),
        },
        "previous_artifact": {
            "evaluation_version": report_doc.get("evaluation_version"),
            "report_version": report_doc.get("report_version"),
            "path": "data/evaluation/skill-extraction-review-report-0.2.0.json",
        },
        "dataset_type": report_doc.get("dataset_type"),
        "dataset_version": report_doc.get("dataset_version"),
        "snapshot_id": report_doc.get("snapshot_id"),
        "taxonomy_version": report_doc.get("taxonomy_version"),
        "matcher_version": report_doc.get("matcher_version"),
        "source": report_doc.get("source"),
        "endpoint": report_doc.get("endpoint"),
        "attribution_url": report_doc.get("attribution_url"),
        "annotation_date": report_doc.get("annotation_date"),
        "sample": dict(sample),
        "definitions": {
            "primary_micro": (
                "pair-level contingency pooled over all non-uncertain final labels: "
                "supported+predicted=TP, supported+not predicted=FN, not_supported+predicted=FP, "
                "not_supported+not predicted=TN; precision=TP/(TP+FP), recall=TP/(TP+FN), "
                "F1=2*P*R/(P+R) with safe zero denominators"
            ),
            "macro": (
                "unweighted mean of per-skill precision/recall/F1 over taxonomy skills with at "
                "least one non-uncertain final-label pair; skills with no defined value (all "
                "labels not_supported) are excluded and listed explicitly"
            ),
            "uncertain": (
                "ambiguous mentions reported separately and excluded from every primary "
                "denominator; zero after the human adjudication"
            ),
            "human_review_decisions": (
                "the seven approved decisions (HR-01..HR-07), each with source id, skill id, "
                "first-pass label when available, original second-pass label, final label, "
                "approval date/source, criterion, preserved reason/question/notes, and "
                "preserved evidence references"
            ),
            "final_for_curated_sample": (
                "the evaluation is final for exactly these 740 pairs of this curated 20-offer "
                "development sample; its scope is limited to this curated sample and does not "
                "generalize to the full market"
            ),
            "historical": (
                "the frozen v0.2.0 account (label distribution, metrics, first-vs-second "
                "comparison, and the 7-item human-review queue) preserved verbatim for audit"
            ),
        },
        "label_distribution": {
            "final": {
                "supported": final_counts["supported"],
                "not_supported": final_counts["not_supported"],
                "uncertain": final_counts["uncertain"],
                "total": len(labels),
            },
            "second_pass": dict((report_doc.get("label_distribution") or {}).get("second_pass", {})),
            "first_draft": dict((report_doc.get("label_distribution") or {}).get("first_draft", {})),
            "note": (
                "final: distribution after the seven approved human decisions; second_pass and "
                "first_draft are the frozen historical distributions (v0.2.0/v0.1.0) preserved "
                "verbatim"
            ),
        },
        "coverage": {
            "definition": (
                "pair coverage = labeled pairs / (dataset records x taxonomy skills); annotated "
                "records = distinct source ids with at least one label"
            ),
            "labeled_pairs": len(labels),
            "non_uncertain_labeled_pairs": len(labels) - final_counts["uncertain"],
            "total_pairs": total_pairs,
            "pair_coverage": len(labels) / total_pairs if total_pairs else None,
            "non_uncertain_pair_coverage": (
                (len(labels) - final_counts["uncertain"]) / total_pairs if total_pairs else None
            ),
            "annotated_records": len(annotated_ids),
            "annotated_record_ids": annotated_ids,
            "annotated_record_coverage": len(annotated_ids) / len(records) if records else None,
        },
        "human_review_queue": {
            "count": 0,
            "items": [],
            "note": (
                "current state: queue closed; the seven approved decisions are recorded "
                "in human_review_decisions and the frozen v0.2.0 queue is preserved under "
                "historical.human_review_queue"
            ),
        },
        "human_review_decisions": list(final_doc["human_review_decisions"]),
        "historical": historical,
        "record_summary": {
            "record_count": len(records),
            "records_reviewed": len(annotated_ids),
            "records_reviewed_coverage": len(annotated_ids) / len(records) if records else None,
            "records_with_evidence": records_with_evidence,
            "records_without_evidence": records_without_evidence,
            "no_evidence_record_ids": sorted(no_evidence_ids) if no_evidence_ids else [],
        },
        "predictions_summary": {
            "predicted_pairs": sum(len(v) for v in predictions_by_record(dataset).values()),
            "unlabeled_predicted_pairs": cont["unlabeled_predicted_pairs"],
            "note": (
                "the final review labels every pair, so no predicted pair is unlabeled; "
                "predicted_pairs counts unique predicted skills per record"
            ),
        },
        "metrics": {
            "primary": {
                "tp": cont["tp"],
                "fp": cont["fp"],
                "fn": cont["fn"],
                "tn": cont["tn"],
                "precision": cont["precision"],
                "recall": cont["recall"],
                "f1": cont["f1"],
                "denominators": {"tp_fn": cont["tp"] + cont["fn"], "tp_fp": cont["tp"] + cont["fp"]},
                "note": (
                    "primary metrics pool every final label (micro); precision/recall are "
                    "undefined (None) when the denominator is zero, F1 is 0.0 when at least one "
                    "of them is defined as zero; metrics are final for this curated 20-offer "
                    "sample only"
                ),
            },
            "micro": {
                "denominator_pairs": len(labels) - final_counts["uncertain"],
                "precision": cont["precision"],
                "recall": cont["recall"],
                "f1": cont["f1"],
                "scope_note": (
                    "micro metrics pool all non-uncertain final labels (each pair contributes "
                    "equally); identical to the primary metrics by definition"
                ),
            },
            "macro": cont["macro"],
            "uncertain": {
                "count": 0,
                "total_uncertain_labels": cont["uncertain"],
                "excluded_note": (
                    "there are no uncertain final labels: the seven queued decisions were all "
                    "approved (uncertain is no longer used in this artifact)"
                ),
            },
        },
        "false_positives": cont["false_positives"],
        "false_negatives": cont["false_negatives"],
        "warnings": [
            "human_review_complete: the seven human-review decisions (HR-01..HR-07) were "
            "approved on 2026-08-02 by explicit project-owner instruction; labels are final for "
            "this curated 20-offer development sample only",
            "all false positives are keyword matches in negative or contextual mentions; the "
            "keyword baseline 0.1.0 does not parse negation (documented; no matcher change was "
            "made)",
            "final metrics describe exactly this curated sample (20 records, one page, one "
            "source); they do not generalize beyond this curated sample",
        ],
        "limitations": [
            "development sample: exactly 20 records from one page (limit=20, offset=0) of one "
            "source, snapshot cap_0370798f7af4b0e3, complete: false; this is not a full feed and "
            "not market coverage",
            "final-for-curated-sample: the evaluation is final for these 740 pairs of this "
            "curated 20-offer sample; its scope is limited to these offers and does not "
            "generalize to the full market",
            "the matcher remains a keyword baseline (keyword-baseline-0.1.0) that does not parse "
            "negation; it is not definitively validated for the full market",
            "the first draft labeled only 60 of 740 pairs; the 680 first-draft-unlabeled pairs "
            "cannot be compared across passes (the historical v0.2.0 comparison is preserved)",
            "no semantic, LLM, or embedding analysis was used for labels or predictions",
        ],
        "guardrails": [
            "labels are final for this curated sample after approved human review; they do not "
            "generalize beyond these 20 offers",
            "no current human-review queue: human_review_queue.count=0; the v0.2.0 queue is preserved historically",
            "uncertain labels are excluded from all primary denominators and reported separately",
            "not_supported means no explicit positive evidence in the reviewed fields, never that "
            "the person or job lacks the skill",
            "no market coverage: one page of one job board is not a market snapshot",
            "no matcher or taxonomy source file was changed by this review",
            "approval date and source are recorded per decision for auditability",
        ],
    }


def materialize_final_review(
    *,
    review_path: str | Path,
    report_path: str | Path,
    dataset_path: str | Path,
    artifact_output_path: str | Path,
    report_output_path: str | Path,
) -> tuple[Path, Path]:
    """Materializa los artefactos de revisión final v0.3.0 adjudicada por humanos.

    Totalmente offline y determinista. Eleva :class:`EvaluationError` cuando las
    entradas congeladas no son el estado fijado v0.2.0 (o alguna decisión no aplica)
    y :class:`DatasetError` cuando una salida cambiaría el contenido existente.
    """
    review_doc = _read_json(review_path, EvaluationError, "v0.2.0 review artifact")
    report_doc = _read_json(report_path, EvaluationError, "v0.2.0 review report")
    dataset = _read_json(dataset_path, DatasetError, "dataset")

    if review_doc.get("evaluation_version") != "skill-extraction-review-0.2.0":
        raise EvaluationError(
            f"la revisión final requiere el artefacto de revisión congelado v0.2.0; se obtuvo "
            f"{review_doc.get('evaluation_version')!r}"
        )
    if review_doc.get("annotation_status") != "draft_second_pass":
        raise EvaluationError(
            f"la revisión final requiere annotation_status draft_second_pass en el artefacto "
            f"congelado; se obtuvo {review_doc.get('annotation_status')!r}"
        )
    if report_doc.get("evaluation_version") != "skill-extraction-review-0.2.0":
        raise EvaluationError(
            f"la revisión final requiere el informe de revisión congelado v0.2.0; se obtuvo "
            f"{report_doc.get('evaluation_version')!r}"
        )
    _check_canonical(Path(review_path), review_doc, "v0.2.0 review artifact")
    _check_canonical(Path(report_path), report_doc, "v0.2.0 review report")

    final_doc = build_final_doc(review_doc, report_doc, dataset)
    final_report = build_final_report(review_doc, report_doc, dataset, final_doc)

    artifact_output = Path(artifact_output_path)
    report_output = Path(report_output_path)
    _write_atomic(artifact_output, _serialize(final_doc))
    _write_atomic(report_output, _serialize(final_report))
    return artifact_output, report_output


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: ``uv run python -m job_market_intelligence.analysis.finalize_review``."""
    parser = argparse.ArgumentParser(
        description=(
            "Materializa los artefactos de revisión final adjudicados por humanos (v0.3.0) desde la "
            "revisión/informe congelados v0.2.0 y el conjunto de datos analítico local. "
            "Totalmente offline y determinista."
        )
    )
    parser.add_argument(
        "--review",
        default=REVIEW_ARTIFACT_DEFAULT_PATH,
        help="ruta del JSON del artefacto de revisión congelado v0.2.0",
    )
    parser.add_argument(
        "--report",
        default=REVIEW_REPORT_DEFAULT_PATH,
        help="ruta del JSON del informe de revisión congelado v0.2.0",
    )
    parser.add_argument(
        "--dataset",
        default=DATASET_DEFAULT_PATH,
        help="ruta del JSON del conjunto de datos analítico",
    )
    parser.add_argument(
        "--artifact-output",
        default=FINAL_ARTIFACT_DEFAULT_PATH,
        help="ruta de salida del artefacto de revisión final",
    )
    parser.add_argument(
        "--report-output",
        default=FINAL_REPORT_DEFAULT_PATH,
        help="ruta de salida del informe de revisión final",
    )
    args = parser.parse_args(argv)
    artifact_path, report_path = materialize_final_review(
        review_path=args.review,
        report_path=args.report,
        dataset_path=args.dataset,
        artifact_output_path=args.artifact_output,
        report_output_path=args.report_output,
    )
    print(f"wrote {artifact_path}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
