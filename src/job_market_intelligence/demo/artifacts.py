"""Carga y normalización tolerantes y testeables de los artefactos demo.

La app del escritorio de evidencia (``app/evidence_desk.py``) lee exactamente
los artefactos locales versionados bajo ``data/``:

- ``data/analytics/development-sample-0.1.0.json`` — 20 ofertas con evidencia
  determinista de palabras clave e informe de calidad incrustado;
- ``data/analytics/descriptive-development-sample-0.1.0.json`` — frecuencia de
  habilidades a nivel de registro, cobertura de categorías, coocurrencia y
  habilidades con cero coincidencias;
- ``data/evaluation/skill-extraction-review-0.3.0.json`` — 740 pares
  ``(source_id, skill_id)`` anotados con una etiqueta final por par
  (``final_label``), las siete decisiones humanas aprobadas y
  ``annotation_status: human_review_complete``;
- ``data/evaluation/skill-extraction-review-report-0.3.0.json`` — las métricas
  finales de la muestra curada, los falsos positivos, el libro de auditoría de
  la revisión humana y una cola actual vacía (el registro histórico v0.2.0
  vive bajo el bloque ``historical``);
- ``data/taxonomy/technical-skills-0.1.0.json`` — la taxonomía de 37 habilidades
  usada como búsqueda de id -> nombre visible/categoría.

Los artefactos históricos v0.2.0 siguen siendo cargables y legibles mediante las
constantes explícitas ``REVIEW_PATH_V020`` / ``REPORT_PATH_V020`` (o cualquier
ruta explícita pasada a los cargadores directos); nunca se sobrescriben.

Contrato de carga:

- Un archivo de artefacto faltante, ilegible o no JSON lanza
  :class:`DemoDataError` (la app muestra un mensaje de recuperación).
- Los datos opcionales por campo degradan a marcadores explícitos — nunca a un
  fallo: ``Untitled role``, ``Unknown company``, ``Not stated``, ``Not disclosed``,
  extracto vacío. Los recuentos mostrados por la UI siempre provienen de los artefactos.
- Las citas de evidencia se verifican de forma defensiva en tiempo de renderizado
  mediante :func:`verify_quote` (``field[char_start:char_end] == exact_quote``).
- El contrato del bundle es de cierre ante fallo: :func:`load_demo_bundle`
  valida el estado curado final fijado (20 registros, 37 habilidades de
  taxonomía, 740 etiquetas, snapshot, versiones, ``human_review_complete``,
  required false, cola vacía, exactamente siete decisiones aprobadas y las
  métricas finales derivadas) y rechaza alcances incompatibles o afirmaciones
  de revisión incompatibles, mientras que los campos opcionales de los
  registros siguen degradando con elegancia.

Este módulo nunca importa Streamlit y nunca modifica artefactos; la validación
de procedencia permanece en los cargadores de la tubería con cierre ante fallo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

#: Raíz del repositorio resuelta desde este archivo (src/job_market_intelligence/demo/).
REPO_ROOT = Path(__file__).resolve().parents[3]

DATASET_PATH = REPO_ROOT / "data" / "analytics" / "development-sample-0.1.0.json"
DESCRIPTIVE_PATH = (
    REPO_ROOT / "data" / "analytics" / "descriptive-development-sample-0.1.0.json"
)
REVIEW_PATH = REPO_ROOT / "data" / "evaluation" / "skill-extraction-review-0.3.0.json"
REPORT_PATH = (
    REPO_ROOT / "data" / "evaluation" / "skill-extraction-review-report-0.3.0.json"
)
#: Artefactos históricos de segunda pasada en borrador (v0.2.0) — nunca se sobrescriben;
#: siguen siendo cargables/legibles mediante estas constantes explícitas o cualquier ruta explícita.
REVIEW_PATH_V020 = REPO_ROOT / "data" / "evaluation" / "skill-extraction-review-0.2.0.json"
REPORT_PATH_V020 = (
    REPO_ROOT / "data" / "evaluation" / "skill-extraction-review-report-0.2.0.json"
)
TAXONOMY_PATH = REPO_ROOT / "data" / "taxonomy" / "technical-skills-0.1.0.json"

# ---------------------------------------------------------------------------
# Contrato del estado demo fijado
#
# El escritorio de evidencia solo puede mostrar este estado exacto. Las constantes
# se usan para fallar con claridad ante artefactos inconsistentes; los recuentos
# mostrados siguen proviniendo de los propios artefactos, nunca de estos valores.
# ---------------------------------------------------------------------------

EXPECTED_DATASET_KIND = "development_sample"
EXPECTED_RECORD_COUNT = 20
EXPECTED_TAXONOMY_SKILL_COUNT = 37
EXPECTED_LABEL_COUNT = 740
EXPECTED_HUMAN_QUEUE_COUNT = 0
EXPECTED_HUMAN_REVIEW_DECISIONS = 7
EXPECTED_SNAPSHOT_ID = "cap_0370798f7af4b0e3"
EXPECTED_DATASET_VERSION = "0.1.0"
EXPECTED_MATCHER_VERSION = "keyword-baseline-0.1.0"
EXPECTED_TAXONOMY_VERSION = "technical-skills-0.1.0"
EXPECTED_EVALUATION_VERSION = "skill-extraction-review-0.3.0"
EXPECTED_ANNOTATION_STATUS = "human_review_complete"
EXPECTED_APPROVAL_DATE = "2026-08-02"
EXPECTED_APPROVAL_SOURCE = "explicit project-owner instruction"
#: Distribución final de etiquetas sobre los 740 pares tras las decisiones aprobadas.
EXPECTED_LABEL_DISTRIBUTION: Mapping[str, int] = {
    "supported": 40,
    "not_supported": 700,
    "uncertain": 0,
}
#: Métricas micro finales sobre los 740 pares (formateadas).
EXPECTED_METRICS: Mapping[str, Any] = {
    "tp": 40,
    "fp": 16,
    "fn": 0,
    "tn": 684,
    "precision": "0.7143",
    "recall": "1.0000",
    "f1": "0.8333",
}
#: Las afirmaciones de estado que implicarían revisión humana/final se rechazan.
FORBIDDEN_FINAL_STATUSES = frozenset({"gold", "human_reviewed", "final", "reviewed"})
#: Enumerado cerrado de etiquetas del artefacto de anotación de segunda pasada.
LABEL_VALUES = frozenset({"supported", "not_supported", "uncertain"})

#: Etiquetas visibles para las ocho categorías de la taxonomía (respaldo: el id crudo).
CATEGORY_LABELS: dict[str, str] = {
    "programming_language": "Programming language",
    "framework_library": "Framework / library",
    "ml_ai": "ML & AI",
    "cloud_platform": "Cloud platform",
    "data_platform": "Data platform",
    "developer_tool": "Developer tool",
    "mobile": "Mobile",
    "security_identity": "Security & identity",
}

_PLACEHOLDER_COMPANY_VALUES = {"", "name", "n/a", "unknown"}


class DemoDataError(RuntimeError):
    """Un archivo de artefacto falta, es ilegible o no es el estado demo fijado."""


def _read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DemoDataError(f"cannot read artifact {path}: {exc}") from exc
    try:
        return json.loads(text)
    except ValueError as exc:
        raise DemoDataError(f"artifact {path} is not valid JSON: {exc}") from exc


def _mapping(raw: Any, label: str) -> dict:
    if not isinstance(raw, dict):
        raise DemoDataError(f"{label} must be a JSON object; got {type(raw).__name__}")
    return raw


def _string(raw: Any) -> str:
    return raw if isinstance(raw, str) else ""


def _string_list(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _int(raw: Any, default: int = 0) -> int:
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else default


# ---------------------------------------------------------------------------
# Taxonomía
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillInfo:
    """Una habilidad de la taxonomía, normalizada para la visualización."""

    skill_id: str
    name: str
    category: str
    keywords: tuple[str, ...]
    aliases: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class TaxonomyInfo:
    """La taxonomía de habilidades técnicas como búsqueda para la visualización."""

    version: str
    skills: tuple[SkillInfo, ...]
    categories: tuple[str, ...]
    category_labels: Mapping[str, str]
    excluded_terms: Mapping[str, str]
    rules: Mapping[str, str] = field(default_factory=dict)

    def skill_by_id(self, skill_id: str) -> SkillInfo | None:
        for skill in self.skills:
            if skill.skill_id == skill_id:
                return skill
        return None

    def skill_name(self, skill_id: str) -> str:
        skill = self.skill_by_id(skill_id)
        return skill.name if skill is not None else skill_id

    def category_label(self, category: str) -> str:
        return self.category_labels.get(category, category)


def load_taxonomy_info(path: Path = TAXONOMY_PATH) -> TaxonomyInfo:
    """Carga el artefacto de taxonomía de forma tolerante (respaldos por entrada)."""
    doc = _mapping(_read_json(path), "taxonomy")
    skills: list[SkillInfo] = []
    categories: set[str] = set()
    for entry in doc.get("skills", []):
        if not isinstance(entry, dict):
            continue
        skill_id = _string(entry.get("skill_id"))
        if not skill_id:
            continue
        name = _string(entry.get("name")) or skill_id
        category = _string(entry.get("category"))
        if category:
            categories.add(category)
        skills.append(
            SkillInfo(
                skill_id=skill_id,
                name=name,
                category=category,
                keywords=_string_list(entry.get("keywords")),
                aliases=_string_list(entry.get("aliases")),
                notes=_string(entry.get("notes")),
            )
        )
    excluded = doc.get("excluded_terms")
    rules_raw = doc.get("rules")
    return TaxonomyInfo(
        version=_string(doc.get("version")) or "unknown",
        skills=tuple(skills),
        categories=tuple(sorted(categories)),
        category_labels=dict(CATEGORY_LABELS),
        excluded_terms={k: _string(v) for k, v in excluded.items()}
        if isinstance(excluded, dict)
        else {},
        rules={k: _string(v) for k, v in rules_raw.items()}
        if isinstance(rules_raw, dict)
        else {},
    )


# ---------------------------------------------------------------------------
# Registros de ofertas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceEntry:
    """Una cita de evidencia del matcher (deduplicada por campo + término coincidente)."""

    skill_id: str
    field: str
    matched_term: str
    term_type: str
    excerpt: str
    occurrence_count: int


@dataclass(frozen=True)
class JobRecord:
    """Un registro de la muestra de desarrollo, normalizado para la visualización."""

    source_id: str
    title_raw: str
    company_raw: str
    company_slug_raw: str
    location_scope: str
    location_restrictions: tuple[str, ...]
    employment_type: str
    seniority: tuple[str, ...]
    categories: tuple[str, ...]
    salary: str
    published_at_utc: str
    expires_at_utc: str
    source_url: str
    application_url: str
    excerpt: str
    description_html: str
    skills: tuple[str, ...]
    evidence: tuple[EvidenceEntry, ...]

    @classmethod
    def from_dict(cls, record: Mapping[str, Any]) -> "JobRecord":
        evidence_raw = record.get("skill_evidence")
        evidence_map = evidence_raw if isinstance(evidence_raw, dict) else {}
        skills_raw = evidence_map.get("skills") or []
        skills = tuple(s for s in skills_raw if isinstance(s, str))
        entries: list[EvidenceEntry] = []
        for entry in evidence_map.get("evidence") or []:
            if not isinstance(entry, dict):
                continue
            entries.append(
                EvidenceEntry(
                    skill_id=_string(entry.get("skill_id")),
                    field=_string(entry.get("field")),
                    matched_term=_string(entry.get("matched_term")),
                    term_type=_string(entry.get("term_type")),
                    excerpt=_string(entry.get("excerpt")),
                    occurrence_count=_int(entry.get("occurrence_count"), 0),
                )
            )
        return cls(
            source_id=_string(record.get("source_id")),
            title_raw=_string(record.get("title_raw")),
            company_raw=_string(record.get("company_raw")),
            company_slug_raw=_string(record.get("company_slug_raw")),
            location_scope=_string(record.get("location_scope")),
            location_restrictions=_string_list(record.get("location_restrictions_raw")),
            employment_type=_string(record.get("employment_type_raw")),
            seniority=_string_list(record.get("seniority_raw")),
            categories=_string_list(record.get("categories_raw")),
            salary=_format_salary(
                record.get("salary_min_raw"),
                record.get("salary_max_raw"),
                record.get("salary_period_raw"),
                record.get("currency_raw"),
            ),
            published_at_utc=_string(record.get("published_at_utc")),
            expires_at_utc=_string(record.get("expires_at_utc")),
            source_url=_string(record.get("source_url")),
            application_url=_string(record.get("application_url")),
            excerpt=_string(record.get("excerpt_raw")),
            description_html=_string(record.get("description_html_raw")),
            skills=skills,
            evidence=tuple(entries),
        )

    @property
    def display_title(self) -> str:
        return self.title_raw or "Untitled role"

    @property
    def display_company(self) -> str:
        if self.company_raw.strip().lower() not in _PLACEHOLDER_COMPANY_VALUES:
            return self.company_raw
        return prettify_slug(self.company_slug_raw)

    @property
    def display_location(self) -> str:
        if self.location_scope == "worldwide":
            return "Worldwide (remote)"
        if self.location_restrictions:
            return "Restricted to: " + ", ".join(self.location_restrictions)
        if self.location_scope == "explicit_ec":
            return "Ecuador"
        if self.location_scope:
            return self.location_scope.replace("_", " ").title()
        return "Not stated"

    def field_value(self, field: str) -> str:
        """El valor de cadena crudo de un campo revisado ('' cuando falta o no es cadena)."""
        return {
            "title_raw": self.title_raw,
            "excerpt_raw": self.excerpt,
            "description_html_raw": self.description_html,
        }.get(field, "")


def prettify_slug(slug: str) -> str:
    """``micro1`` -> ``Micro1``; entrada vacía -> ``Unknown company``."""
    cleaned = slug.strip()
    if not cleaned:
        return "Unknown company"
    return cleaned[0].upper() + cleaned[1:]


def _format_salary(min_raw: Any, max_raw: Any, period_raw: Any, currency_raw: Any) -> str:
    if min_raw is None and max_raw is None:
        return "Not disclosed"
    currency = _string(currency_raw).upper()
    prefix = f"{currency} " if currency else ""
    if min_raw is not None and max_raw is not None:
        span = f"{prefix}{min_raw:,} - {prefix}{max_raw:,}"
    elif min_raw is not None:
        span = f"{prefix}{min_raw:,}+"
    else:
        span = f"up to {prefix}{max_raw:,}"
    period = _string(period_raw).lower()
    if period and period not in ("", "n/a"):
        span += f" per {period}"
    return span


@dataclass(frozen=True)
class DemoDataset:
    """El conjunto de datos analítico de desarrollo, normalizado para la visualización."""

    records: tuple[JobRecord, ...]
    sample: Mapping[str, Any]
    capture_identity: Mapping[str, Any]
    quality_report: Mapping[str, Any]
    dataset_version: str
    matcher_version: str
    dataset_kind: str = ""
    taxonomy_version: str = ""

    @property
    def record_count(self) -> int:
        return len(self.records)

    def record_by_source(self, source_id: str) -> JobRecord | None:
        for record in self.records:
            if record.source_id == source_id:
                return record
        return None


def load_dataset(path: Path = DATASET_PATH) -> DemoDataset:
    doc = _mapping(_read_json(path), "dataset")
    records = tuple(
        JobRecord.from_dict(record)
        for record in doc.get("records", [])
        if isinstance(record, dict)
    )
    return DemoDataset(
        records=records,
        sample=doc.get("sample") if isinstance(doc.get("sample"), dict) else {},
        capture_identity=(
            doc.get("capture_identity") if isinstance(doc.get("capture_identity"), dict) else {}
        ),
        quality_report=(
            doc.get("quality_report") if isinstance(doc.get("quality_report"), dict) else {}
        ),
        dataset_version=_string(doc.get("dataset_version")),
        matcher_version=_string(doc.get("matcher_version")),
        dataset_kind=_string(doc.get("dataset_kind")),
        taxonomy_version=_string(doc.get("taxonomy_version")),
    )


# ---------------------------------------------------------------------------
# Etiquetas de revisión de segunda pasada
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewEvidence:
    """Una cita de evidencia de la segunda pasada con desplazamientos de caracteres de medio intervalo abierto."""

    field: str
    exact_quote: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ReviewLabel:
    """Un par ``(source_id, skill_id)`` anotado.

    ``label`` es la etiqueta de registro: la etiqueta final en el artefacto v0.3.0
    (``final_label``) y la etiqueta de segunda pasada en el artefacto histórico
    v0.2.0 (que no tiene ``final_label``). ``second_pass_label`` conserva la
    etiqueta original de la segunda pasada siempre que el artefacto la incluya.
    """

    source_id: str
    skill_id: str
    label: str  # supported | not_supported | uncertain (label of record)
    second_pass_label: str
    final_label: str
    evidence: tuple[ReviewEvidence, ...]
    reviewed_fields: tuple[str, ...]
    reason: str
    human_review_question: str
    notes: str
    adjudication_id: str = ""

    @property
    def is_uncertain(self) -> bool:
        return self.label == "uncertain"

    @property
    def is_adjudicated(self) -> bool:
        return bool(self.adjudication_id)

    @property
    def adjudicated_to_supported(self) -> bool:
        return self.is_adjudicated and self.label == "supported"


@dataclass(frozen=True)
class ReviewSet:
    """El artefacto de revisión de 740 etiquetas, normalizado para la visualización.

    En el artefacto v0.3.0 actual, ``label`` es la etiqueta final (``final_label``)
    y la etiqueta original de la segunda pasada se conserva en
    ``second_pass_label``; el artefacto histórico v0.2.0 se carga con
    ``label == second_pass_label == final_label``.
    """

    evaluation_version: str
    annotation_status: str
    human_review_required: bool
    labels: tuple[ReviewLabel, ...]
    snapshot_id: str = ""
    dataset_type: str = ""
    taxonomy_version: str = ""
    human_review_complete: bool = False
    approval: Mapping[str, Any] = field(default_factory=dict)
    previous_artifact: Mapping[str, Any] = field(default_factory=dict)
    human_review_decisions: tuple[Mapping[str, Any], ...] = ()

    def label_counts(self) -> dict[str, int]:
        """Distribución de la etiqueta de registro (final en v0.3.0), enumerado cerrado."""
        counts: dict[str, int] = {"supported": 0, "not_supported": 0, "uncertain": 0}
        for label in self.labels:
            counts[label.label] = counts.get(label.label, 0) + 1
        return counts

    def second_pass_label_counts(self) -> dict[str, int]:
        """Distribución de las etiquetas originales conservadas de la segunda pasada, enumerado cerrado."""
        counts: dict[str, int] = {"supported": 0, "not_supported": 0, "uncertain": 0}
        for label in self.labels:
            counts[label.second_pass_label] = counts.get(label.second_pass_label, 0) + 1
        return counts

    def labels_for(self, source_id: str) -> tuple[ReviewLabel, ...]:
        return tuple(label for label in self.labels if label.source_id == source_id)

    def label_for(self, source_id: str, skill_id: str) -> ReviewLabel | None:
        for label in self.labels:
            if label.source_id == source_id and label.skill_id == skill_id:
                return label
        return None


def load_review(path: Path = REVIEW_PATH) -> ReviewSet:
    doc = _mapping(_read_json(path), "review")
    labels: list[ReviewLabel] = []
    for entry in doc.get("labels", []):
        if not isinstance(entry, dict):
            continue
        evidence = tuple(
            ReviewEvidence(
                field=_string(ev.get("field")),
                exact_quote=_string(ev.get("exact_quote")),
                char_start=_int(ev.get("char_start")),
                char_end=_int(ev.get("char_end")),
            )
            for ev in entry.get("evidence", [])
            if isinstance(ev, dict)
        )
        second_pass = _string(entry.get("label")) or "not_supported"
        final = _string(entry.get("final_label")) or second_pass
        labels.append(
            ReviewLabel(
                source_id=_string(entry.get("source_id")),
                skill_id=_string(entry.get("skill_id")),
                label=final,
                second_pass_label=second_pass,
                final_label=final,
                evidence=evidence,
                reviewed_fields=_string_list(entry.get("reviewed_fields")),
                reason=_string(entry.get("reason")),
                human_review_question=_string(entry.get("human_review_question")),
                notes=_string(entry.get("notes")),
                adjudication_id=_string(entry.get("adjudication_id")),
            )
        )
    decisions = doc.get("human_review_decisions", [])
    return ReviewSet(
        evaluation_version=_string(doc.get("evaluation_version")),
        annotation_status=_string(doc.get("annotation_status")) or "unknown",
        human_review_required=doc.get("human_review_required") is True,
        labels=tuple(labels),
        snapshot_id=_string(doc.get("snapshot_id")),
        dataset_type=_string(doc.get("dataset_type")),
        taxonomy_version=_string(doc.get("taxonomy_version")),
        human_review_complete=doc.get("human_review_complete") is True,
        approval=doc.get("approval") if isinstance(doc.get("approval"), dict) else {},
        previous_artifact=(
            doc.get("previous_artifact") if isinstance(doc.get("previous_artifact"), dict) else {}
        ),
        human_review_decisions=tuple(
            item for item in decisions if isinstance(item, dict)
        ),
    )


# ---------------------------------------------------------------------------
# Informe de revisión (métricas provisionales y cola de revisión humana)
# ---------------------------------------------------------------------------


def format_metric(value: Any) -> str:
    """``0.7450980392156863`` -> ``0.7451``; ``None`` -> ``n/a``."""
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def format_metric_es(value: Any) -> str:
    """Formato decimal español para la superficie pública (coma decimal).

    ``0.7450980392156863`` -> ``0,7451``; ``1.0`` -> ``1,0``; ``None`` -> ``n/d``.
    Recorta los ceros finales y conserva al menos un decimal. El formato
    técnico con punto queda en :func:`format_metric` (solo «Detalles técnicos»).
    """
    if value is None:
        return "n/d"
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text.replace(".", ",")


#: Palabras humanas en español para el enumerado cerrado de la segunda pasada.
VERDICT_LABELS_ES: dict[str, str] = {
    "supported": "respaldado",
    "not_supported": "no respaldado",
    "uncertain": "incierto",
}


def verdict_es(label: str) -> str:
    """``supported`` -> ``respaldado``; valores desconocidos degradan al crudo."""
    return VERDICT_LABELS_ES.get(label, label)


#: Nombres legibles en español de los campos de texto revisados.
FIELD_LABELS_ES: dict[str, str] = {
    "title_raw": "Título",
    "excerpt_raw": "Extracto",
    "categories_raw": "Categorías",
    "description_html_raw": "Descripción",
}


def field_es(field: str) -> str:
    """``title_raw`` -> ``Título``; desconocidos degradan a «Campo de la oferta»."""
    return FIELD_LABELS_ES.get(field, "Campo de la oferta")


@dataclass(frozen=True)
class ReviewReport:
    """El informe de revisión determinista, normalizado para la visualización.

    En el artefacto v0.3.0 actual ``human_queue`` está vacía (recuento 0) y las
    decisiones auditables viven en ``human_review_decisions``; el registro
    congelado v0.2.0 (distribución de etiquetas, métricas, comparación
    primer-borrador-vs-segunda-pasada y la cola de 7 elementos) se conserva
    textualmente bajo ``historical``.
    """

    annotation_status: str
    human_review_required: bool
    label_distribution: Mapping[str, Any]
    metrics: Mapping[str, Any]
    false_positives: tuple[Mapping[str, Any], ...]
    false_negatives: tuple[Mapping[str, Any], ...]
    human_queue: tuple[Mapping[str, Any], ...]
    first_vs_second: Mapping[str, Any]
    uncertainty: Mapping[str, Any]
    coverage: Mapping[str, Any]
    definitions: Mapping[str, Any]
    limitations: tuple[str, ...]
    guardrails: tuple[str, ...]
    warnings: tuple[str, ...]
    sample: Mapping[str, Any]
    snapshot_id: str = ""
    dataset_type: str = ""
    taxonomy_version: str = ""
    human_review_complete: bool = False
    approval: Mapping[str, Any] = field(default_factory=dict)
    previous_artifact: Mapping[str, Any] = field(default_factory=dict)
    human_review_decisions: tuple[Mapping[str, Any], ...] = ()
    historical: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_provisional(self) -> bool:
        return self.annotation_status == "draft_second_pass" and self.human_review_required

    @property
    def is_final_for_curated_sample(self) -> bool:
        return (
            self.annotation_status == "human_review_complete"
            and self.human_review_complete
            and not self.human_review_required
        )

    @property
    def primary_metrics(self) -> dict[str, Any]:
        primary = self.metrics.get("primary")
        return dict(primary) if isinstance(primary, dict) else {}

    @property
    def macro_metrics(self) -> dict[str, Any]:
        macro = self.metrics.get("macro")
        return dict(macro) if isinstance(macro, dict) else {}

    @property
    def historical_first_vs_second(self) -> Mapping[str, Any]:
        historical = self.historical.get("first_vs_second")
        return historical if isinstance(historical, dict) else {}

    @property
    def historical_human_queue(self) -> Mapping[str, Any]:
        historical = self.historical.get("human_review_queue")
        return historical if isinstance(historical, dict) else {}


def load_report(path: Path = REPORT_PATH) -> ReviewReport:
    doc = _mapping(_read_json(path), "review report")
    metrics = doc.get("metrics")
    historical = doc.get("historical")
    decisions = doc.get("human_review_decisions", [])
    return ReviewReport(
        annotation_status=_string(doc.get("annotation_status")) or "unknown",
        human_review_required=doc.get("human_review_required") is True,
        label_distribution=doc.get("label_distribution", {}),
        metrics=metrics if isinstance(metrics, dict) else {},
        false_positives=tuple(
            entry for entry in doc.get("false_positives", []) if isinstance(entry, dict)
        ),
        false_negatives=tuple(
            entry for entry in doc.get("false_negatives", []) if isinstance(entry, dict)
        ),
        human_queue=tuple(
            entry
            for entry in doc.get("human_review_queue", {}).get("items", [])
            if isinstance(entry, dict)
        ),
        first_vs_second=doc.get("first_vs_second", {}),
        uncertainty=doc.get("uncertainty", {}),
        coverage=doc.get("coverage", {}),
        definitions=doc.get("definitions", {}),
        limitations=tuple(item for item in doc.get("limitations", []) if isinstance(item, str)),
        guardrails=tuple(item for item in doc.get("guardrails", []) if isinstance(item, str)),
        warnings=tuple(item for item in doc.get("warnings", []) if isinstance(item, str)),
        sample=doc.get("sample", {}),
        snapshot_id=_string(doc.get("snapshot_id")),
        dataset_type=_string(doc.get("dataset_type")),
        taxonomy_version=_string(doc.get("taxonomy_version")),
        human_review_complete=doc.get("human_review_complete") is True,
        approval=doc.get("approval") if isinstance(doc.get("approval"), dict) else {},
        previous_artifact=(
            doc.get("previous_artifact") if isinstance(doc.get("previous_artifact"), dict) else {}
        ),
        human_review_decisions=tuple(
            item for item in decisions if isinstance(item, dict)
        ),
        historical=historical if isinstance(historical, dict) else {},
    )


# ---------------------------------------------------------------------------
# Análisis descriptivo (panorama de habilidades)
# ---------------------------------------------------------------------------


def load_descriptive(path: Path = DESCRIPTIVE_PATH) -> dict:
    return _mapping(_read_json(path), "descriptive analysis")


def skill_frequency(descriptive: Mapping[str, Any]) -> dict[str, int]:
    """Frecuencia de habilidades a nivel de registro: skill_id -> registros coincidentes distintos."""
    raw = descriptive.get("skill_frequency")
    if not isinstance(raw, dict):
        return {}
    freq = {k: _int(v) for k, v in raw.items()}
    return dict(sorted(freq.items(), key=lambda item: (-item[1], item[0])))


def category_coverage(descriptive: Mapping[str, Any]) -> list[dict]:
    """Entradas de cobertura de categorías: category, records, matched_skill_count."""
    raw = descriptive.get("category_coverage")
    categories = raw.get("categories") if isinstance(raw, dict) else None
    if not isinstance(categories, list):
        return []
    return [entry for entry in categories if isinstance(entry, dict)]


def zero_match_skills(descriptive: Mapping[str, Any]) -> list[dict]:
    """Habilidades de la taxonomía con cero registros coincidentes (no son evidencia de ausencia)."""
    raw = descriptive.get("zero_match_skills")
    skills = raw.get("skills") if isinstance(raw, dict) else None
    if not isinstance(skills, list):
        return []
    return [entry for entry in skills if isinstance(entry, dict)]


# ---------------------------------------------------------------------------
# Estados de máquina (los tres estados visibles que el escritorio debe mostrar)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoStatus:
    """Los tres estados de máquina que el escritorio muestra, derivados de los artefactos."""

    demo_ready: bool
    evaluation_final: bool
    human_reviewed: bool

    @property
    def labels(self) -> tuple[str, ...]:
        return (
            "demo-ready" if self.demo_ready else "demo-not-ready",
            "evaluation-final" if self.evaluation_final else "evaluation-not-final",
            "human-reviewed" if self.human_reviewed else "human-review-pending",
        )


def derive_status(report: ReviewReport) -> DemoStatus:
    """Deriva los estados de máquina visibles a partir del informe de revisión.

    El estado v0.3.0 actual deriva ``evaluation-final`` y ``human-reviewed``
    (final para la muestra curada; nunca una afirmación de mercado). Las
    comprobaciones finales de arranque y navegador se completaron para esta
    superficie local de muestra curada; por lo tanto ``demo-ready`` es verdadero
    como puerta de entrega, pero nunca se muestra como token de máquina público.
    """
    human_reviewed = report.is_final_for_curated_sample
    evaluation_final = human_reviewed and report.annotation_status not in FORBIDDEN_FINAL_STATUSES
    return DemoStatus(
        demo_ready=evaluation_final,
        evaluation_final=evaluation_final,
        human_reviewed=human_reviewed,
    )


# ---------------------------------------------------------------------------
# Paquete
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoBundle:
    """Todo lo que el escritorio de evidencia muestra, cargado desde los cinco artefactos."""

    taxonomy: TaxonomyInfo
    dataset: DemoDataset
    descriptive: dict
    review: ReviewSet
    report: ReviewReport
    status: DemoStatus


def validate_bundle(bundle: DemoBundle) -> None:
    """Falla con claridad cuando los artefactos no son el estado curado final fijado.

    Los campos opcionales de los registros conservan sus respaldos elegantes; esto
    comprueba solo el contrato estricto: los recuentos fijados, el snapshot, las
    versiones, la forma de la muestra, el enumerado cerrado de etiquetas, el estado
    ``human_review_complete`` (required false, cola vacía), exactamente siete
    decisiones humanas aprobadas, la distribución final de etiquetas y las métricas
    finales derivadas. Se rechazan alcances incompatibles o afirmaciones de estado
    de revisión incompatibles.
    """
    problems: list[str] = []

    def check(ok: bool, message: str) -> None:
        if not ok:
            problems.append(message)

    ds, tx, rv, rp = bundle.dataset, bundle.taxonomy, bundle.review, bundle.report

    check(
        ds.dataset_kind == EXPECTED_DATASET_KIND,
        f"dataset_kind {ds.dataset_kind!r} != {EXPECTED_DATASET_KIND!r}",
    )
    check(
        ds.record_count == EXPECTED_RECORD_COUNT,
        f"record count {ds.record_count} != {EXPECTED_RECORD_COUNT}",
    )
    check(
        ds.dataset_version == EXPECTED_DATASET_VERSION,
        f"dataset version {ds.dataset_version!r} != {EXPECTED_DATASET_VERSION!r}",
    )
    check(
        ds.matcher_version == EXPECTED_MATCHER_VERSION,
        f"matcher version {ds.matcher_version!r} != {EXPECTED_MATCHER_VERSION!r}",
    )
    check(
        ds.taxonomy_version == EXPECTED_TAXONOMY_VERSION,
        f"dataset taxonomy_version {ds.taxonomy_version!r} != {EXPECTED_TAXONOMY_VERSION!r}",
    )
    check(
        ds.capture_identity.get("snapshot_id") == EXPECTED_SNAPSHOT_ID,
        f"snapshot {ds.capture_identity.get('snapshot_id')!r} != {EXPECTED_SNAPSHOT_ID!r}",
    )
    sample = ds.sample
    check(sample.get("complete") is False, f"sample.complete is {sample.get('complete')!r}, expected false")
    check(
        sample.get("records") == EXPECTED_RECORD_COUNT,
        f"sample.records {sample.get('records')!r} != {EXPECTED_RECORD_COUNT}",
    )
    check(
        (sample.get("page"), sample.get("limit"), sample.get("offset")) == (1, 20, 0),
        f"sample shape page/limit/offset {sample.get('page')!r}/{sample.get('limit')!r}/{sample.get('offset')!r} != 1/20/0",
    )

    check(
        tx.version == EXPECTED_TAXONOMY_VERSION,
        f"taxonomy version {tx.version!r} != {EXPECTED_TAXONOMY_VERSION!r}",
    )
    check(
        len(tx.skills) == EXPECTED_TAXONOMY_SKILL_COUNT,
        f"taxonomy skill count {len(tx.skills)} != {EXPECTED_TAXONOMY_SKILL_COUNT}",
    )

    check(
        rv.annotation_status == EXPECTED_ANNOTATION_STATUS,
        f"annotation_status {rv.annotation_status!r} != {EXPECTED_ANNOTATION_STATUS!r}",
    )
    check(rv.human_review_required is False, "human_review_required is not false")
    check(
        rv.human_review_complete is True and rp.human_review_complete is True,
        "human_review_complete is not true on both review and report",
    )
    check(
        rv.annotation_status not in FORBIDDEN_FINAL_STATUSES
        and rp.annotation_status not in FORBIDDEN_FINAL_STATUSES,
        "artifact claims an incompatible review status",
    )
    check(
        len(rv.labels) == EXPECTED_LABEL_COUNT,
        f"label count {len(rv.labels)} != {EXPECTED_LABEL_COUNT}",
    )
    unknown_labels = sorted({label.label for label in rv.labels} - LABEL_VALUES)
    check(not unknown_labels, f"labels outside the closed enum: {unknown_labels}")
    check(
        rv.label_counts() == EXPECTED_LABEL_DISTRIBUTION,
        f"final label distribution {rv.label_counts()} != {EXPECTED_LABEL_DISTRIBUTION}",
    )
    check(
        rv.second_pass_label_counts().get("uncertain", 0) == 5
        and rv.second_pass_label_counts().get("supported", 0) == 38,
        "preserved second-pass labels do not match the historical v0.2.0 distribution",
    )
    check(
        rv.snapshot_id == EXPECTED_SNAPSHOT_ID and rp.snapshot_id == EXPECTED_SNAPSHOT_ID,
        f"review/report snapshot {rv.snapshot_id!r}/{rp.snapshot_id!r} != {EXPECTED_SNAPSHOT_ID!r}",
    )
    check(
        rv.taxonomy_version == EXPECTED_TAXONOMY_VERSION
        and rp.taxonomy_version == EXPECTED_TAXONOMY_VERSION,
        "review/report taxonomy_version does not match the pinned taxonomy",
    )
    check(
        rv.dataset_type == EXPECTED_DATASET_KIND and rp.dataset_type == EXPECTED_DATASET_KIND,
        f"review/report dataset_type is not {EXPECTED_DATASET_KIND!r}",
    )
    check(
        rv.evaluation_version == EXPECTED_EVALUATION_VERSION,
        f"evaluation version {rv.evaluation_version!r} != {EXPECTED_EVALUATION_VERSION!r}",
    )
    check(
        len(rp.human_queue) == EXPECTED_HUMAN_QUEUE_COUNT,
        f"human-review queue has {len(rp.human_queue)} items, expected {EXPECTED_HUMAN_QUEUE_COUNT}",
    )
    decisions = rp.human_review_decisions
    check(
        len(decisions) == EXPECTED_HUMAN_REVIEW_DECISIONS,
        f"human-review decisions {len(decisions)} != {EXPECTED_HUMAN_REVIEW_DECISIONS}",
    )
    for item in decisions:
        check(
            item.get("final_label") in LABEL_VALUES
            and item.get("approval_date") == EXPECTED_APPROVAL_DATE
            and item.get("approval_source") == EXPECTED_APPROVAL_SOURCE
            and bool(item.get("criterion")),
            f"decision {item.get('item_id')!r} is missing final label, approval date/source, or criterion",
        )
    approval = rp.approval
    check(
        approval.get("date") == EXPECTED_APPROVAL_DATE
        and approval.get("source") == EXPECTED_APPROVAL_SOURCE
        and approval.get("decisions_count") == EXPECTED_HUMAN_REVIEW_DECISIONS,
        f"report approval metadata {approval} does not match the approved record",
    )
    historical = rp.historical
    check(
        historical.get("evaluation_version") == "skill-extraction-review-0.2.0"
        and (historical.get("human_review_queue") or {}).get("count") == 7,
        "historical v0.2.0 block is missing or its 7-item queue is not preserved",
    )
    metrics = rp.primary_metrics
    for key, expected in EXPECTED_METRICS.items():
        if key in ("precision", "recall", "f1"):
            actual = format_metric(metrics.get(key))
        else:
            actual = metrics.get(key)
        check(actual == expected, f"metric {key} is {actual!r}, expected {expected!r}")

    if problems:
        raise DemoDataError(
            "demo artifacts are not the pinned final curated state: "
            + "; ".join(problems)
        )


def load_demo_bundle(
    root: Path = REPO_ROOT, paths: Mapping[str, Path] | None = None
) -> DemoBundle:
    """Carga, normaliza y valida los cinco artefactos demo.

    ``root`` permite que las pruebas y la app apunten explícitamente a la raíz del
    repositorio; ``paths`` sobreescribe archivos de artefacto individuales (claves:
    ``dataset``, ``descriptive``, ``review``, ``report``, ``taxonomy``).
    """
    resolved = {
        "dataset": DATASET_PATH,
        "descriptive": DESCRIPTIVE_PATH,
        "review": REVIEW_PATH,
        "report": REPORT_PATH,
        "taxonomy": TAXONOMY_PATH,
    }
    if paths is not None:
        for key, value in paths.items():
            if key in resolved and isinstance(value, Path):
                resolved[key] = value
    if root != REPO_ROOT:
        for key in resolved:
            resolved[key] = root / resolved[key].relative_to(REPO_ROOT)
    report = load_report(resolved["report"])
    bundle = DemoBundle(
        taxonomy=load_taxonomy_info(resolved["taxonomy"]),
        dataset=load_dataset(resolved["dataset"]),
        descriptive=load_descriptive(resolved["descriptive"]),
        review=load_review(resolved["review"]),
        report=report,
        status=derive_status(report),
    )
    validate_bundle(bundle)
    return bundle


# ---------------------------------------------------------------------------
# Verificación de citas (defensiva, usada en tiempo de renderizado)
# ---------------------------------------------------------------------------


def verify_quote(value: str, char_start: int, char_end: int, exact_quote: str) -> bool:
    """Verdadero cuando ``value[char_start:char_end] == exact_quote`` (medio intervalo abierto, dentro de límites)."""
    if char_start < 0 or char_end < char_start or char_end > len(value):
        return False
    return value[char_start:char_end] == exact_quote
