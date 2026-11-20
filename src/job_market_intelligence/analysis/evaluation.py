"""Evaluación de extracción de habilidades de borrador para la muestra de desarrollo.

Determinista y completamente offline.

Este módulo valida el artefacto de evaluación de borrador comprometido
(``data/evaluation/skill-extraction-development-0.1.0.json``) contra el
conjunto de datos analítico de desarrollo y la taxonomía versionada, compara las
etiquetas escritas manualmente con las predicciones existentes de la línea base
de palabras clave (``skill_evidence.skills``) y calcula las métricas primarias.
No consulta páginas raw, manifests, respuestas de la API ni la red, y no lee el
reloj del sistema: la fecha de anotación es la fecha fija del repositorio
``2026-08-02``.

Semántica de etiquetas (documentada en ``annotation_method`` del artefacto):

- **supported**: existe al menos una entrada de evidencia exacta; el evaluador
  verifica ``field[char_start:char_end] == exact_quote`` contra el valor exacto
  del campo en el registro analítico (offsets half-open al estilo de Python y
  únicamente campos de texto: ``title_raw``, ``excerpt_raw``,
  ``description_html_raw``).
- **not_supported**: no existe evidencia positiva explícita en los campos
  revisados (nunca significa «la persona o el puesto carece de la habilidad»);
  la evidencia está vacía.
- **uncertain**: mención genuinamente ambigua; puede incluir una cita ambigua
  exacta, pero se excluye de todos los denominadores primarios y se informa por
  separado.

Contingencia (solo sobre pares etiquetados no uncertain; cada habilidad predicha
cuenta como máximo una vez por registro):

- supported + predicha -> TP
- supported + no predicha -> FN
- not_supported + predicha -> FP
- not_supported + no predicha -> TN (se informa, pero no es obligatoria en el titular)
- los pares sin etiqueta se excluyen por completo: una predicción sin etiqueta
  no es un falso positivo ni un negativo de ningún tipo.

Métricas:

- **primary / micro**: agrupada sobre todos los pares etiquetados no uncertain;
  precisión, recall y F1 con denominadores seguros (``None`` cuando el
  denominador es cero; F1 es ``0.0`` cuando al menos una de precisión/recall
  está definida como 0).
- **macro**: media no ponderada de precisión/recall/F1 por habilidad sobre el
  alcance determinista explícito: habilidades de la taxonomía con al menos un
  par etiquetado no uncertain. Una habilidad cuyas etiquetas son todas
  ``not_supported`` (sin etiqueta positiva gold ni predicción) no tiene métrica
  por habilidad definida y se excluye de las medias, con listado explícito en
  ``skills_excluded_undefined``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import EvaluationError
from .taxonomy import Taxonomy

#: Versión del diseño del conjunto de evaluación (subir cuando cambie el diseño).
EVALUATION_VERSION = "skill-extraction-development-0.1.0"

#: El discriminador de tipo del artefacto.
EVALUATION_KIND = "skill_extraction_evaluation"

#: El único estado permitido: etiquetas de borrador, nunca gold ni revisadas por humanos.
EVALUATION_STATUS = "draft_evaluation"

#: El tipo de conjunto de datos documentado que anota la evaluación.
DATASET_TYPE = "development_sample"

#: La identidad de snapshot documentada de la muestra de desarrollo.
SNAPSHOT_ID = "cap_0370798f7af4b0e3"

#: La versión de taxonomía documentada de la muestra de desarrollo.
TAXONOMY_VERSION = "technical-skills-0.1.0"

#: Fecha de anotación fija (fecha del repositorio/sesión; nunca una llamada al reloj de pared).
ANNOTATION_DATE = "2026-08-02"

#: Enumerado de etiquetas cerrado.
LABEL_VALUES = ("supported", "not_supported", "uncertain")

#: Conjunto cerrado de campos de evidencia: solo los campos de cadena exactos pueden llevar offsets.
#: ``categories_raw`` es una lista JSON y no es utilizable para evidencia con offsets.
EVIDENCE_FIELDS = ("title_raw", "excerpt_raw", "description_html_raw")

#: Contrato documentado de la muestra de desarrollo (ver el artefacto del conjunto de datos).
SAMPLE_RECORDS = 20
SAMPLE_PAGE = 1
SAMPLE_LIMIT = 20
SAMPLE_OFFSET = 0

#: Rutas de artefacto por defecto, relativas a la raíz del repositorio.
EVALUATION_ARTIFACT_DEFAULT_PATH = "data/evaluation/skill-extraction-development-0.1.0.json"
REPORT_ARTIFACT_DEFAULT_PATH = "data/evaluation/skill-extraction-development-report-0.1.0.json"

_REQUIRED_METADATA = (
    "evaluation_version",
    "evaluation_status",
    "dataset_type",
    "snapshot_id",
    "taxonomy_version",
    "source",
    "attribution_url",
    "annotation_date",
    "annotation_method",
)


@dataclass(frozen=True)
class Evidence:
    """Una cita exacta con offsets mitad-abiertos dentro del valor de un campo del conjunto de datos."""

    field: str
    exact_quote: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class LabelEntry:
    """Una etiqueta ``(source_id, skill_id)`` escrita a mano."""

    source_id: str
    skill_id: str
    label: str
    evidence: tuple[Evidence, ...]
    notes: str | None = None


@dataclass(frozen=True)
class EvaluationSet:
    """Un artefacto de evaluación de borrador validado (metadatos + etiquetas)."""

    evaluation_version: str
    evaluation_kind: str | None
    evaluation_status: str
    dataset_type: str
    dataset_version: str | None
    snapshot_id: str
    taxonomy_version: str
    matcher_version: str | None
    source: str
    endpoint: str | None
    attribution_url: str
    annotation_date: str
    annotation_method: str
    sample: Mapping[str, Any]
    labels: tuple[LabelEntry, ...]


def _require_string(doc: Mapping[str, Any], key: str, label: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} debe ser una cadena no vacía; se obtuvo {value!r}")
    return value


def _optional_string(doc: Mapping[str, Any], key: str) -> str | None:
    value = doc.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"'{key}' debe ser una cadena no vacía cuando está presente; se obtuvo {value!r}")
    return value


def _parse_sample(raw: Any) -> dict:
    if not isinstance(raw, dict):
        raise EvaluationError("'sample' debe ser un objeto JSON")
    for key, check in (
        ("records", lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0),
        ("page", lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1),
        ("limit", lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 1),
        ("offset", lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0),
    ):
        if key not in raw or not check(raw[key]):
            raise EvaluationError(f"sample.{key} debe ser un entero válido; se obtuvo {raw.get(key)!r}")
    if "complete" not in raw or not isinstance(raw["complete"], bool):
        raise EvaluationError(f"sample.complete debe ser un booleano; se obtuvo {raw.get('complete')!r}")
    return dict(raw)


def _parse_evidence(raw: Any) -> tuple[Evidence, ...]:
    if not isinstance(raw, list):
        raise EvaluationError("'evidence' debe ser un arreglo JSON")
    entries: list[Evidence] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise EvaluationError("cada entrada de evidencia debe ser un objeto JSON")
        field_name = entry.get("field")
        if field_name not in EVIDENCE_FIELDS:
            raise EvaluationError(
                f"evidence 'field' debe ser uno de {EVIDENCE_FIELDS}; se obtuvo {field_name!r} "
                "(categories_raw es una lista JSON y no puede llevar evidencia con offsets)"
            )
        quote = entry.get("exact_quote")
        if not isinstance(quote, str) or not quote:
            raise EvaluationError("evidence 'exact_quote' debe ser una cadena no vacía")
        start = entry.get("char_start")
        end = entry.get("char_end")
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise EvaluationError(f"evidence 'char_start' debe ser un entero no negativo; se obtuvo {start!r}")
        if not isinstance(end, int) or isinstance(end, bool) or end < start:
            raise EvaluationError(
                f"evidence 'char_end' debe ser un entero >= char_start; se obtuvo {end!r} con start {start!r}"
            )
        entries.append(Evidence(field=field_name, exact_quote=quote, char_start=start, char_end=end))
    return tuple(entries)


def _parse_labels(raw: Any) -> tuple[LabelEntry, ...]:
    if not isinstance(raw, list) or not raw:
        raise EvaluationError("'labels' debe ser un arreglo JSON no vacío")
    labels: list[LabelEntry] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise EvaluationError("cada entrada de etiqueta debe ser un objeto JSON")
        source_id = _require_string(entry, "source_id", "label 'source_id'")
        skill_id = _require_string(entry, "skill_id", "label 'skill_id'")
        value = entry.get("label")
        if value not in LABEL_VALUES:
            raise EvaluationError(
                f"la etiqueta debe ser uno de {LABEL_VALUES}; se obtuvo {value!r} para ({source_id}, {skill_id})"
            )
        pair = (source_id, skill_id)
        if pair in seen:
            raise EvaluationError(f"no se permite una etiqueta duplicada para ({source_id}, {skill_id})")
        seen.add(pair)
        evidence = _parse_evidence(entry.get("evidence", []))
        if value == "supported" and not evidence:
            raise EvaluationError(
                f"la etiqueta supported ({source_id}, {skill_id}) debe llevar al menos una entrada de evidencia exacta"
            )
        if value == "not_supported" and evidence:
            raise EvaluationError(
                f"la etiqueta not_supported ({source_id}, {skill_id}) debe tener evidencia vacía; "
                "la evidencia está reservada para la evidencia positiva explícita"
            )
        notes_raw = entry.get("notes")
        notes = notes_raw if isinstance(notes_raw, str) and notes_raw.strip() else None
        labels.append(
            LabelEntry(
                source_id=source_id,
                skill_id=skill_id,
                label=value,
                evidence=evidence,
                notes=notes,
            )
        )
    return tuple(labels)


def evaluation_from_dict(doc: Mapping[str, Any]) -> EvaluationSet:
    """Valida un artefacto de evaluación parseado (comprobaciones de esquema de cierre ante fallos)."""
    if not isinstance(doc, dict):
        raise EvaluationError(f"el documento de evaluación debe ser un objeto JSON; se obtuvo {type(doc).__name__}")
    for key in _REQUIRED_METADATA:
        _require_string(doc, key, f"'{key}'")
    if doc["evaluation_status"] != EVALUATION_STATUS:
        raise EvaluationError(
            f"evaluation_status debe ser exactamente 'draft_evaluation' (estas etiquetas son de borrador, "
            f"nunca gold ni revisadas por humanos); se obtuvo {doc['evaluation_status']!r}"
        )
    return EvaluationSet(
        evaluation_version=doc["evaluation_version"],
        evaluation_kind=_optional_string(doc, "evaluation_kind"),
        evaluation_status=doc["evaluation_status"],
        dataset_type=doc["dataset_type"],
        dataset_version=_optional_string(doc, "dataset_version"),
        snapshot_id=doc["snapshot_id"],
        taxonomy_version=doc["taxonomy_version"],
        matcher_version=_optional_string(doc, "matcher_version"),
        source=doc["source"],
        endpoint=_optional_string(doc, "endpoint"),
        attribution_url=doc["attribution_url"],
        annotation_date=doc["annotation_date"],
        annotation_method=doc["annotation_method"],
        sample=_parse_sample(doc.get("sample")),
        labels=_parse_labels(doc.get("labels")),
    )


def load_evaluation(path: str | Path) -> EvaluationSet:
    """Carga y valida un artefacto de evaluación de borrador desde un archivo JSON."""
    try:
        raw_text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"no se puede leer el artefacto de evaluación {path}: {exc}") from exc
    try:
        doc = json.loads(raw_text)
    except ValueError as exc:
        raise EvaluationError(f"el artefacto de evaluación {path} no es JSON válido: {exc}") from exc
    return evaluation_from_dict(doc)


def resolve_quote_span(text: str, quote: str) -> tuple[int, int] | None:
    """Devuelve el primer tramo mitad-abierto ``(start, end)`` de ``quote`` en ``text``.

    Se usa para redactar y validar las citas escritas por humanos; nunca lee
    la salida del matcher.
    """
    if not isinstance(text, str) or not isinstance(quote, str) or not quote:
        return None
    start = text.find(quote)
    if start < 0:
        return None
    return start, start + len(quote)


def validate_evaluation(evaluation: EvaluationSet, dataset: Mapping[str, Any], taxonomy: Taxonomy) -> None:
    """Falla de forma cerrada cuando la evaluación no anota este conjunto de datos exacto.

    Comprueba el acuerdo de metadatos evaluación/conjunto de datos (tipo de
    conjunto de datos, identidad de snapshot, versión de taxonomía, forma de
    muestra), la existencia del id de fuente y del id de habilidad de cada
    etiqueta y el contrato de evidencia exacto: los campos de evidencia deben
    ser campos de cadena existentes del registro y
    ``field[char_start:char_end] == exact_quote`` con offsets no negativos y
    dentro de límites.
    """
    if not isinstance(dataset, dict):
        raise EvaluationError("el conjunto de datos debe ser un objeto JSON")
    if evaluation.dataset_type != dataset.get("dataset_kind"):
        raise EvaluationError(
            f"desajuste de tipo de conjunto de datos: la evaluación anota {evaluation.dataset_type!r} pero el "
            f"conjunto de datos declara {dataset.get('dataset_kind')!r}"
        )
    if evaluation.taxonomy_version != dataset.get("taxonomy_version"):
        raise EvaluationError(
            f"desajuste de versión de taxonomía: la evaluación declara "
            f"{evaluation.taxonomy_version!r} pero el conjunto de datos declara "
            f"{dataset.get('taxonomy_version')!r}"
        )
    if evaluation.taxonomy_version != taxonomy.version:
        raise EvaluationError(
            f"desajuste de versión de taxonomía: la evaluación declara "
            f"{evaluation.taxonomy_version!r} pero el artefacto de taxonomía es {taxonomy.version!r}"
        )
    identity = dataset.get("capture_identity")
    if not isinstance(identity, dict) or identity.get("snapshot_id") != evaluation.snapshot_id:
        raise EvaluationError(
            f"desajuste de snapshot: la evaluación declara {evaluation.snapshot_id!r} pero el conjunto "
            f"de datos lleva {identity.get('snapshot_id') if isinstance(identity, dict) else None!r}"
        )
    sample = dataset.get("sample")
    if not isinstance(sample, dict):
        raise EvaluationError("el conjunto de datos no tiene un objeto de metadatos 'sample'")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise EvaluationError("el conjunto de datos no tiene una lista 'records'")
    for label_name in ("records", "page", "limit", "offset", "complete"):
        if evaluation.sample.get(label_name) != sample.get(label_name):
            raise EvaluationError(
                f"desajuste de muestra: la evaluación declara sample.{label_name} = "
                f"{evaluation.sample.get(label_name)!r} pero el conjunto de datos declara "
                f"{sample.get(label_name)!r}"
            )
    if evaluation.sample.get("records") != len(records):
        raise EvaluationError(
            f"desajuste de muestra: la evaluación declara {evaluation.sample.get('records')} registros "
            f"pero el conjunto de datos lleva {len(records)}"
        )

    record_by_source = {record.get("source_id"): record for record in records if isinstance(record, dict)}
    if len(record_by_source) != len(records):
        raise EvaluationError("el conjunto de datos contiene ids de fuente duplicados; se rechaza evaluar")

    for entry in evaluation.labels:
        record = record_by_source.get(entry.source_id)
        if record is None:
            raise EvaluationError(
                f"el source_id {entry.source_id!r} de la etiqueta no existe en los registros del conjunto de datos"
            )
        if taxonomy.skill_by_id(entry.skill_id) is None:
            raise EvaluationError(
                f"el skill_id {entry.skill_id!r} de la etiqueta no existe en la taxonomía {taxonomy.version}"
            )
        for ev in entry.evidence:
            value = record.get(ev.field)
            if not isinstance(value, str):
                raise EvaluationError(
                    f"el campo de evidencia {ev.field!r} no es una cadena en el registro {entry.source_id!r}; "
                    f"se obtuvo {type(value).__name__}"
                )
            if ev.char_end > len(value):
                raise EvaluationError(
                    f"evidence char_end {ev.char_end} excede la longitud de {ev.field} "
                    f"({len(value)}) en el registro {entry.source_id!r}"
                )
            actual = value[ev.char_start : ev.char_end]
            if actual != ev.exact_quote:
                raise EvaluationError(
                    f"desajuste de cita de evidencia en el registro {entry.source_id!r} para la habilidad "
                    f"{entry.skill_id!r}: {ev.field}[{ev.char_start}:{ev.char_end}] = {actual!r} "
                    f"pero la etiqueta registra {ev.exact_quote!r}"
                )


def predictions_by_record(dataset: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """Habilidades predichas únicas por registro (una habilidad cuenta como máximo una vez por registro)."""
    predictions: dict[str, tuple[str, ...]] = {}
    for record in dataset.get("records", []):
        if not isinstance(record, dict):
            continue
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            continue
        skills = (record.get("skill_evidence") or {}).get("skills") or []
        seen: set[str] = set()
        unique: list[str] = []
        for skill_id in skills:
            if isinstance(skill_id, str) and skill_id not in seen:
                seen.add(skill_id)
                unique.append(skill_id)
        predictions[source_id] = tuple(unique)
    return predictions


def _matcher_evidence(record: Mapping[str, Any], skill_id: str) -> dict:
    for entry in (record.get("skill_evidence") or {}).get("evidence", []):
        if isinstance(entry, dict) and entry.get("skill_id") == skill_id:
            return {
                "field": entry.get("field"),
                "matched_term": entry.get("matched_term"),
                "term_type": entry.get("term_type"),
                "excerpt": entry.get("excerpt"),
            }
    raise EvaluationError(
        "no se encontró evidencia del matcher para la habilidad predicha "
        f"{skill_id!r} en el registro {record.get('source_id')!r}"
    )


def build_contingency(evaluation: EvaluationSet, dataset: Mapping[str, Any]) -> dict:
    """Contingencia a nivel de par sobre los pares etiquetados no uncertain.

    Las etiquetas uncertain se cuentan por separado y no aparecen en ninguna
    celda; los pares sin etiqueta se excluyen por completo (una predicción sin
    etiqueta nunca es un negativo). Los falsos positivos llevan la evidencia
    propia del matcher (campo, término, extracto); los falsos negativos llevan
    la evidencia de la etiqueta gold (citas exactas).
    """
    predictions = predictions_by_record(dataset)
    record_by_source = {
        record.get("source_id"): record for record in dataset.get("records", []) if isinstance(record, dict)
    }
    labels_by_pair = {(entry.source_id, entry.skill_id): entry for entry in evaluation.labels}

    tp = fp = fn = tn = uncertain = 0
    per_skill: dict[str, dict[str, int]] = {}
    false_positives: list[dict] = []
    false_negatives: list[dict] = []

    for entry in evaluation.labels:
        predicted = entry.skill_id in predictions.get(entry.source_id, ())
        if entry.label == "uncertain":
            uncertain += 1
            continue
        if entry.label == "supported":
            if predicted:
                tp += 1
                cell = "tp"
            else:
                fn += 1
                cell = "fn"
                false_negatives.append(
                    {
                        "source_id": entry.source_id,
                        "skill_id": entry.skill_id,
                        "label": entry.label,
                        "gold_evidence": [
                            {
                                "field": ev.field,
                                "exact_quote": ev.exact_quote,
                                "char_start": ev.char_start,
                                "char_end": ev.char_end,
                            }
                            for ev in entry.evidence
                        ],
                        "notes": entry.notes,
                    }
                )
        else:  # not_supported
            if predicted:
                fp += 1
                cell = "fp"
                false_positives.append(
                    {
                        "source_id": entry.source_id,
                        "skill_id": entry.skill_id,
                        "label": entry.label,
                        "matcher_evidence": _matcher_evidence(
                            record_by_source.get(entry.source_id, {}), entry.skill_id
                        ),
                        "notes": entry.notes,
                    }
                )
            else:
                tn += 1
                cell = "tn"
        counts = per_skill.setdefault(entry.skill_id, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        counts[cell] += 1

    unlabeled_predicted_pairs = 0
    for source_id, skills in predictions.items():
        for skill_id in skills:
            if (source_id, skill_id) not in labels_by_pair:
                unlabeled_predicted_pairs += 1

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "uncertain": uncertain,
        "labeled_pairs": len(evaluation.labels),
        "non_uncertain_labeled_pairs": tp + fp + fn + tn,
        "per_skill": dict(sorted(per_skill.items())),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "unlabeled_predicted_pairs": unlabeled_predicted_pairs,
    }


def _precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    """Precisión/recall/F1 seguros frente a denominador cero.

    La precisión y el recall son ``None`` cuando su denominador es cero; F1 es
    ``None`` solo cuando ambos están indefinidos, y ``0.0`` cuando al menos uno
    de ellos está definido como cero.
    """
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None and recall is None:
        f1: float | None = None
    else:
        pv = precision or 0.0
        rv = recall or 0.0
        f1 = 2 * pv * rv / (pv + rv) if pv + rv else 0.0
    return precision, recall, f1


def compute_metrics(evaluation: EvaluationSet, dataset: Mapping[str, Any], taxonomy: Taxonomy) -> dict:
    """Grupos de métricas primaria/micro, macro y uncertain con alcances explícitos."""
    cont = build_contingency(evaluation, dataset)
    tp, fp, fn, tn = cont["tp"], cont["fp"], cont["fn"], cont["tn"]
    precision, recall, f1 = _precision_recall_f1(tp, fp, fn)

    scope = sorted(skill_id for skill_id, counts in cont["per_skill"].items() if sum(counts.values()) > 0)
    per_skill_metrics: dict[str, dict] = {}
    defined: list[str] = []
    for skill_id in scope:
        counts = cont["per_skill"][skill_id]
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
            "macro scope: taxonomy skills with at least one non-uncertain labeled pair; per-skill "
            "precision/recall/F1 are computed over that skill's own labeled pairs and then averaged "
            "unweighted over the skills whose value is defined; a skill whose labels are all "
            "not_supported has no positive gold or prediction and no defined per-skill metric"
        ),
        "skills_in_scope": scope,
        "skills_excluded_undefined": sorted(skill_id for skill_id in scope if skill_id not in defined),
        "precision": mean([per_skill_metrics[skill_id]["precision"] for skill_id in defined]),
        "recall": mean([per_skill_metrics[skill_id]["recall"] for skill_id in defined]),
        "f1": mean([per_skill_metrics[skill_id]["f1"] for skill_id in defined]),
        "per_skill": per_skill_metrics,
    }

    return {
        "primary": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "denominators": {"tp_fp": tp + fp, "tp_fn": tp + fn},
            "note": (
                "primary metrics pool every non-uncertain labeled pair (micro); precision/recall are "
                "undefined (None) when the denominator is zero, F1 is 0.0 when at least one of them "
                "is defined as 0"
            ),
        },
        "micro": {
            "scope_note": (
                "micro metrics pool all non-uncertain labeled pairs (each pair contributes equally); "
                "identical to the primary metrics by definition"
            ),
            "denominator_pairs": cont["non_uncertain_labeled_pairs"],
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "macro": macro,
        "uncertain": {
            "count": cont["uncertain"],
            "excluded_note": (
                "uncertain labels are reported separately and excluded from all primary denominators "
                "and from the macro scope"
            ),
        },
    }


def build_report(evaluation: EvaluationSet, dataset: Mapping[str, Any], taxonomy: Taxonomy) -> dict:
    """Construye el informe de evaluación determinista para el conjunto de borrador confirmado."""
    validate_evaluation(evaluation, dataset, taxonomy)
    cont = build_contingency(evaluation, dataset)
    metrics = compute_metrics(evaluation, dataset, taxonomy)

    records = dataset.get("records", [])
    total_pairs = len(records) * len(taxonomy.skills)
    annotated_ids = sorted({entry.source_id for entry in evaluation.labels})
    report = dataset.get("quality_report") or {}
    coverage = report.get("skill_coverage") or {}
    records_with_evidence = coverage.get("records_with_evidence")
    records_without_evidence = coverage.get("records_without_evidence")
    no_evidence_ids = coverage.get("records_no_evidence")
    if records_with_evidence is None:
        evidence_statuses = [
            "matched"
            for record in records
            if isinstance(record.get("skill_evidence"), dict)
            and record["skill_evidence"].get("evidence_status") == "matched"
        ]
        records_with_evidence = len(evidence_statuses)
        records_without_evidence = len(records) - records_with_evidence
        no_evidence_ids = sorted(
            record["source_id"]
            for record in records
            if isinstance(record.get("skill_evidence"), dict)
            and record["skill_evidence"].get("evidence_status") == "no_evidence"
        )

    warnings = [
        "draft_evaluation: labels were independently drafted from direct source-text inspection and "
        "are NOT human-reviewed or gold; every metric on this report is provisional",
    ]
    if cont["fn"] == 0:
        warnings.append(
            "this draft contains no false negatives (FN=0): the curated positives were chosen where the "
            "keyword baseline is strong; this reflects the curated draft set, not the market"
        )
    sample = dataset.get("sample") or {}
    return {
        "report_version": "0.1.0",
        "evaluation_version": evaluation.evaluation_version,
        "evaluation_kind": evaluation.evaluation_kind,
        "evaluation_status": evaluation.evaluation_status,
        "dataset_type": evaluation.dataset_type,
        "dataset_version": evaluation.dataset_version,
        "snapshot_id": evaluation.snapshot_id,
        "taxonomy_version": evaluation.taxonomy_version,
        "matcher_version": evaluation.matcher_version,
        "source": evaluation.source,
        "endpoint": evaluation.endpoint,
        "attribution_url": evaluation.attribution_url,
        "annotation_date": evaluation.annotation_date,
        "sample": {
            "records": evaluation.sample.get("records"),
            "page": evaluation.sample.get("page"),
            "limit": evaluation.sample.get("limit"),
            "offset": evaluation.sample.get("offset"),
            "complete": evaluation.sample.get("complete"),
            "total_count": sample.get("total_count"),
            "warning": evaluation.sample.get("warning"),
            "limitations": list(evaluation.sample.get("limitations", [])),
        },
        "definitions": {
            "primary_micro": (
                "pair-level contingency pooled over all non-uncertain labeled pairs: "
                "supported+predicted=TP, supported+not predicted=FN, not_supported+predicted=FP, "
                "not_supported+not predicted=TN; precision=TP/(TP+FP), recall=TP/(TP+FN), "
                "F1=2*P*R/(P+R) with safe zero denominators"
            ),
            "macro": (
                "unweighted mean of per-skill precision/recall/F1 over taxonomy skills with at least "
                "one non-uncertain labeled pair; skills with no defined value (all labels "
                "not_supported) are excluded and listed explicitly"
            ),
            "uncertain": ("ambiguous mentions reported separately and excluded from every primary denominator"),
            "coverage": ("labeled pairs over all dataset-record x taxonomy-skill pairs, plus annotated records"),
        },
        "label_distribution": {
            "supported": cont["tp"] + cont["fn"],
            "not_supported": cont["fp"] + cont["tn"],
            "uncertain": cont["uncertain"],
            "total": cont["labeled_pairs"],
        },
        "coverage": {
            "definition": (
                "pair coverage = labeled pairs / (dataset records x taxonomy skills); annotated "
                "records = distinct source ids with at least one label"
            ),
            "labeled_pairs": cont["labeled_pairs"],
            "non_uncertain_labeled_pairs": cont["non_uncertain_labeled_pairs"],
            "total_pairs": total_pairs,
            "pair_coverage": cont["labeled_pairs"] / total_pairs if total_pairs else None,
            "non_uncertain_pair_coverage": (cont["non_uncertain_labeled_pairs"] / total_pairs if total_pairs else None),
            "annotated_records": len(annotated_ids),
            "annotated_record_ids": annotated_ids,
            "annotated_record_coverage": len(annotated_ids) / len(records) if records else None,
        },
        "record_summary": {
            "record_count": len(records),
            "records_with_evidence": records_with_evidence,
            "records_without_evidence": records_without_evidence,
            "no_evidence_record_ids": sorted(no_evidence_ids) if no_evidence_ids else [],
        },
        "predictions_summary": {
            "predicted_pairs": sum(len(skills) for skills in predictions_by_record(dataset).values()),
            "unlabeled_predicted_pairs": cont["unlabeled_predicted_pairs"],
            "note": (
                "predicted pairs without a label are excluded from the metrics entirely; they are "
                "never treated as false positives or negatives"
            ),
        },
        "metrics": metrics,
        "false_positives": cont["false_positives"],
        "false_negatives": cont["false_negatives"],
        "warnings": warnings,
        "limitations": [
            "development sample: exactly 20 records from one page (limit=20, offset=0) of one source, "
            "snapshot cap_0370798f7af4b0e3, complete: false; this is not a full feed and not market "
            "coverage",
            f"label coverage is partial: {cont['non_uncertain_labeled_pairs']} of {total_pairs} "
            "non-uncertain labeled pairs in this draft set",
            "the keyword baseline 0.1.0 does not parse negation; the draft false positives are AI "
            "mentions in roles that explicitly state AI experience is not required",
            "no semantic, LLM, or embedding analysis was used for labels or predictions",
        ],
        "guardrails": [
            "labels are draft, not gold or human-reviewed; metrics are provisional",
            "uncertain labels are excluded from all primary denominators and reported separately",
            "unlabeled pairs are excluded from the metrics, never treated as false positives or negatives",
            "not_supported means no explicit positive evidence in the reviewed fields, never that the "
            "person or job lacks the skill",
            "no market coverage: one page of one job board is not a market snapshot",
        ],
    }


def serialize_evaluation(doc: Mapping[str, Any]) -> bytes:
    """Serialización JSON canónica en UTF-8 para el artefacto de evaluación.

    Claves ordenadas y sangría de 2 espacios.
    """
    return (json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def serialize_report(report: Mapping[str, Any]) -> bytes:
    """Serialización JSON determinista en UTF-8 para el informe de evaluación."""
    return (json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
