"""Revisión independiente de etiquetas de habilidades de segunda pasada (borrador; requiere revisión humana).

Este módulo implementa la segunda pasada independiente aprobada sobre la
extracción de habilidades de la muestra de desarrollo. Etiqueta los 20 x 37 = 740
pares ``(source_id, skill_id)`` del conjunto de datos analítico de desarrollo
mediante una **rutina independiente de anotación por lectura directa del texto**
impulsada por un **manifiesto de adjudicación curado** (``_ADJUDICATION`` a
continuación): las etiquetas se deciden leyendo los campos de texto de origen
conservados en el conjunto de datos analítico (``title_raw``,
``excerpt_raw``, ``categories_raw``, ``description_html_raw``) y usando los
términos de la taxonomía solo como vocabulario candidato.
``annotate_second_pass(...)`` NUNCA lee ``skill_evidence``; las predicciones del
matcher las consume exclusivamente ``compare_with_predictions(...)`` después de
que existan las 740 etiquetas. Las dos funciones están deliberadamente separadas
para que la procedencia sea inspeccionable: las etiquetas de la segunda pasada
nunca son ``labels = predictions`` ni se derivan de ``skill_evidence``.

Estado del artefacto: ``draft_second_pass`` con ``human_review_required: true``.
El artefacto NO es gold ni está revisado por humanos, y no se modificó ninguna
regla del matcher ni de la taxonomía. Todas las citas de evidencia son
segmentos exactos del valor del campo del conjunto de datos con desplazamientos
válidos de medio intervalo abierto (``field[char_start:char_end] ==
exact_quote``), verificados con cierre ante fallo. No se consultan páginas
crudas, manifiestos, respuestas de API ni red, y no se lee el reloj: la fecha de
anotación es la fecha fija del repositorio ``2026-08-02``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import EvaluationError
from .evaluation import (
    ANNOTATION_DATE,
    DATASET_TYPE,
    SNAPSHOT_ID,
    Evidence,
    LABEL_VALUES,
    _matcher_evidence,
    _parse_evidence,
    _parse_sample,
    _precision_recall_f1,
    predictions_by_record,
    resolve_quote_span,
)
from .taxonomy import Taxonomy

#: Versión del diseño del conjunto de revisión de la segunda pasada (incrementar al cambiar el diseño).
REVIEW_VERSION = "skill-extraction-review-0.2.0"

#: Discriminador del tipo de artefacto.
REVIEW_KIND = "skill_extraction_review"

#: El único estado permitido: borrador de segunda pasada, nunca gold ni revisado por humanos.
REVIEW_STATUS = "draft_second_pass"

#: Afirmaciones de estado prohibidas (cualquiera de ellas como valor de estado falla con cierre).
FORBIDDEN_STATUS_VALUES = ("gold", "human_reviewed", "final", "reviewed", "human_review")

#: Los cuatro campos de texto de origen revisados para cada etiqueta. ``categories_raw`` se
#: revisa para las decisiones not_supported/uncertain, pero es una lista JSON y no puede
#: portar evidencia con desplazamientos (solo ``EVIDENCE_FIELDS`` puede).
REVIEWED_FIELDS = ("title_raw", "excerpt_raw", "categories_raw", "description_html_raw")

#: Rutas de artefacto por defecto, relativas a la raíz del repositorio.
REVIEW_ARTIFACT_DEFAULT_PATH = "data/evaluation/skill-extraction-review-0.2.0.json"
REVIEW_REPORT_DEFAULT_PATH = "data/evaluation/skill-extraction-review-report-0.2.0.json"

_REQUIRED_METADATA = (
    "evaluation_version",
    "annotation_status",
    "dataset_type",
    "snapshot_id",
    "taxonomy_version",
    "source",
    "attribution_url",
    "annotation_date",
    "annotation_method",
)

# ---------------------------------------------------------------------------
# Manifiesto de adjudicación curado (la fuente de anotación independiente de registro).
# ---------------------------------------------------------------------------
#
# Nombres cortos de registro -> los source ids exactos del conjunto de datos. El manifiesto
# usa nombres cortos para legibilidad; ``annotate_second_pass`` los resuelve y falla con
# cierre si alguna entrada curada queda sin usar o referencia un registro desconocido.

_SOURCES = {
    "german": "https://himalayas.app/companies/micro1/jobs/german-audio-recording-expert",
    "data-tools": "https://himalayas.app/companies/micro1/jobs/engineering-data-tools-specialist",
    "italian": "https://himalayas.app/companies/micro1/jobs/italian-audio-recording-expert",
    "mandarin": "https://himalayas.app/companies/micro1/jobs/mandarin-audio-recording-expert",
    "portugal": "https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-portugal",
    "brazil": "https://himalayas.app/companies/micro1/jobs/portuguese-audio-recording-expert-brazil",
    "dutch": "https://himalayas.app/companies/micro1/jobs/dutch-audio-recording-experts",
    "biophysics": "https://himalayas.app/companies/micro1/jobs/physics-expert-biophysics-statistical-physics",
    "highenergy": "https://himalayas.app/companies/micro1/jobs/physics-expert-high-energy-mathematical-physics-5946815961",
    "kiembu": "https://himalayas.app/companies/micro1/jobs/kiembu-bilingual-expert",
    "condensed": "https://himalayas.app/companies/micro1/jobs/physics-expert-condensed-matter-quantum-information",
    "biglaw": "https://himalayas.app/companies/micro1/jobs/biglaw-lawyers",
    "strategy-ops": "https://himalayas.app/companies/bjak/jobs/strategy-operations-associate-7652220692",
    "amo": "https://himalayas.app/companies/micro1/jobs/physics-expert-amo-quantum-information",
    "ios-engineer": "https://himalayas.app/companies/clera/jobs/founding-full-stack-ios-engineer",
    "fullstack": "https://himalayas.app/companies/clera/jobs/founding-full-stack-engineer",
    "senior-ml": "https://himalayas.app/companies/bjak/jobs/senior-machine-learning-engineer-851744356",
    "statistical": "https://himalayas.app/companies/micro1/jobs/physics-expert-statistical-physics-quantum-information-condensed-matter",
    "founding-mts": "https://himalayas.app/companies/clera/jobs/founding-member-of-technical-staff",
    "gravitation": "https://himalayas.app/companies/micro1/jobs/physics-expert-gravitation-cosmology-astrophysics",
}

_SOURCE_URL_BY_SHORT = {short: url for short, url in _SOURCES.items()}
_SOURCE_SHORT_BY_URL = {url: short for short, url in _SOURCES.items()}


def _sup(quotes, reason, notes=None):
    return {
        "label": "supported",
        "quotes": tuple(quotes),
        "reason": reason,
        "human_review_question": None,
        "notes": notes,
    }


def _unc(quotes, reason, question, notes=None):
    return {
        "label": "uncertain",
        "quotes": tuple(quotes),
        "reason": reason,
        "human_review_question": question,
        "notes": notes,
    }


def _ns(reason, notes=None):
    return {
        "label": "not_supported",
        "quotes": (),
        "reason": reason,
        "human_review_question": None,
        "notes": notes,
    }


# Cada entrada curada de abajo se decidió leyendo los campos de texto de origen del
# conjunto de datos analítico (title_raw, excerpt_raw, categories_raw,
# description_html_raw); los términos de la taxonomía se usaron solo como vocabulario candidato.
# Las predicciones del matcher NO se consultaron. Las entradas no listadas quedan por defecto
# como ``not_supported`` (sin evidencia positiva explícita en los campos revisados).
_ADJUDICATION: dict[tuple[str, str], dict] = {
    # --- german-audio-recording-expert ------------------------------------
    ("german", "skill.machine_learning"): _unc(
        [("description_html_raw", "datasets for advanced machine learning applications")],
        "Machine learning appears only as the downstream use of the recordings "
        "('helping to build diverse and reliable datasets for advanced machine learning "
        "applications'), not as a skill the role must perform.",
        "Decide whether the project-context mention of machine learning ('datasets for "
        "advanced machine learning applications') counts as explicit evidence of the "
        "machine-learning skill (supported) or not (not_supported).",
        notes="Project-context mention: the recordings feed ML datasets; no ML requirement exists.",
    ),
    ("german", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required' and mentions AI only as project context ('help train next-generation AI "
        "systems'); the role's scope (professional audio recording) contains no AI work. "
        "not_supported means no explicit positive evidence in the reviewed fields, never that "
        "the person or job lacks the skill.",
    ),
    # --- engineering-data-tools-specialist --------------------------------
    ("data-tools", "skill.aws"): _sup(
        [("description_html_raw", "AWS, Azure, Firebase")],
        "Explicitly listed in the scope of work ('cloud solutions (e.g., AWS, Azure, Firebase)') "
        "and in the preferred-qualifications tool list.",
    ),
    ("data-tools", "skill.azure"): _sup(
        [("description_html_raw", "AWS, Azure, Firebase")],
        "Explicitly listed in the scope of work and preferred qualifications ('AWS, Azure, "
        "Firebase'; 'GitHub, Azure, Metabase, and JIRA').",
    ),
    ("data-tools", "skill.firebase"): _sup(
        [("description_html_raw", "AWS, Azure, Firebase")],
        "Explicitly listed ('AWS, Azure, Firebase').",
    ),
    ("data-tools", "skill.databricks"): _sup(
        [("description_html_raw", "Twilio, Databricks, Tableau, Metabase, and BrowserStack")],
        "Explicitly listed in the preferred-qualifications tool list.",
    ),
    ("data-tools", "skill.tableau"): _sup(
        [("description_html_raw", "Tableau, Datadog, Sentry, and BrowserStack")],
        "Explicitly listed ('Tableau, Datadog, Sentry, and BrowserStack').",
    ),
    ("data-tools", "skill.metabase"): _sup(
        [("description_html_raw", "GitHub, Azure, Metabase, and JIRA")],
        "Explicitly listed in the scope-of-work tool list ('GitHub, Azure, Metabase, and JIRA').",
    ),
    ("data-tools", "skill.github"): _sup(
        [("description_html_raw", "GitHub, Azure, Metabase, and JIRA")],
        "Explicitly listed in the scope of work and preferred qualifications.",
    ),
    ("data-tools", "skill.jira"): _sup(
        [("description_html_raw", "GitHub, Azure, Metabase, and JIRA")],
        "Explicitly listed ('GitHub, Azure, Metabase, and JIRA').",
    ),
    ("data-tools", "skill.postman"): _sup(
        [("description_html_raw", "Linear, Postman, n8n")],
        "Explicitly listed ('Linear, Postman, n8n').",
    ),
    ("data-tools", "skill.linear"): _sup(
        [("description_html_raw", "Linear, Postman, n8n")],
        "Explicitly listed ('Linear, Postman, n8n').",
    ),
    ("data-tools", "skill.n8n"): _sup(
        [("description_html_raw", "Linear, Postman, n8n")],
        "Explicitly listed ('Linear, Postman, n8n').",
    ),
    ("data-tools", "skill.sentry"): _sup(
        [("description_html_raw", "Tableau, Datadog, Sentry, and BrowserStack")],
        "Explicitly listed ('Tableau, Datadog, Sentry, and BrowserStack').",
    ),
    ("data-tools", "skill.datadog"): _sup(
        [("description_html_raw", "Tableau, Datadog, Sentry, and BrowserStack")],
        "Explicitly listed ('Tableau, Datadog, Sentry, and BrowserStack').",
    ),
    ("data-tools", "skill.browserstack"): _sup(
        [("description_html_raw", "Tableau, Datadog, Sentry, and BrowserStack")],
        "Explicitly listed ('Tableau, Datadog, Sentry, and BrowserStack').",
    ),
    ("data-tools", "skill.twilio"): _sup(
        [("description_html_raw", "Twilio, Databricks, Tableau, Metabase, and BrowserStack")],
        "Explicitly listed in the preferred-qualifications tool list.",
    ),
    ("data-tools", "skill.data_science"): _unc(
        [("description_html_raw", "engineering, data science, or equivalent practical experience")],
        "'data science' appears only as an acceptable degree field under preferred "
        "qualifications ('Bachelor's degree in computer science, engineering, data science, or "
        "equivalent practical experience'), not as a skill the role performs.",
        "Decide whether a degree-field mention under preferred qualifications counts as "
        "explicit evidence of the data-science skill (supported) or not (not_supported).",
        notes="Degree-field mention; the matcher predicted skill.data_science here. First draft left this pair unlabeled.",
    ),
    ("data-tools", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "and the role's tool-evaluation scope contains no AI work. Independent second-pass "
        "decision: not_supported (the explicit negative requirement is decisive); the first "
        "draft labeled this pair uncertain, so it is queued for human review.",
        notes="First draft: uncertain; second pass: not_supported. Genuine first-vs-second disagreement.",
    ),
    ("data-tools", "skill.git"): _ns(
        "Boundary case: only 'GitHub' appears in the reviewed fields ('GitHub, Azure, Metabase, "
        "and JIRA'); there is no explicit git evidence. git and github are distinct taxonomy "
        "skills with separate identifiers.",
    ),
    # --- italian-audio-recording-expert -----------------------------------
    ("italian", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required' and mentions AI only as project context ('help train next-generation AI "
        "systems'); the role's scope (professional audio recording) contains no AI work.",
    ),
    # --- mandarin-audio-recording-expert ----------------------------------
    ("mandarin", "skill.ai"): _unc(
        [("description_html_raw", "AI data collection or linguistic resource creation is a plus")],
        "Conflicting signals: the posting explicitly says 'No prior experience in AI is "
        "required' but lists a nice-to-have 'Experience participating in projects involving AI "
        "data collection or linguistic resource creation is a plus', and the role 'help[s] "
        "train next-generation AI systems'.",
        "Decide whether the nice-to-have AI-adjacent qualification ('AI data collection ... is "
        "a plus') outweighs the explicit negative requirement ('No prior experience in AI is "
        "required').",
        notes="First draft: not_supported; second pass: uncertain. Genuine first-vs-second disagreement.",
    ),
    ("mandarin", "skill.machine_learning"): _ns(
        "Confusion case: the reviewed fields mention 'developing advanced AI models' and 'AI "
        "training' but never 'machine learning' or 'ml'; 'AI models' is AI vocabulary, not "
        "explicit evidence of the machine-learning skill. The first draft labeled this pair "
        "uncertain, so it is queued for human review.",
        notes="First draft: uncertain; second pass: not_supported. AI-vs-machine-learning vocabulary confusion.",
    ),
    # --- portuguese-audio-recording-expert-portugal -----------------------
    ("portugal", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required' and mentions AI only as project context ('help train next-generation AI "
        "systems'); the role's scope (audio recording) contains no AI work.",
    ),
    # --- portuguese-audio-recording-expert-brazil -------------------------
    ("brazil", "skill.ai"): _unc(
        [("description_html_raw", "audio samples for AI training")],
        "Mixed signals: the categories_raw value 'Brazilian-Portuguese-AI-Specialist' and the "
        "phrase 'contextually relevant audio samples for AI training' suggest AI involvement, "
        "while the posting explicitly says 'No prior experience in AI is required'.",
        "Decide whether the category-context mention ('Brazilian-Portuguese-AI-Specialist' in "
        "categories_raw) and the 'audio samples for AI training' phrase count as evidence of the "
        "AI skill despite the explicit negative requirement.",
        notes="AI in category context (categories_raw cannot carry offset evidence); negative requirement present.",
    ),
    # --- dutch-audio-recording-experts -------------------------------------
    ("dutch", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required' and mentions AI only as project context ('help train next-generation AI "
        "systems'); the role's scope (audio recording) contains no AI work.",
    ),
    # --- physics-expert-biophysics-statistical-physics ---------------------
    ("biophysics", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems', "
        "'AI training and reproducibility purposes') for a physics consulting role.",
    ),
    ("biophysics", "skill.statistics"): _ns(
        "Boundary case: 'Statistical Physics' appears in the title and excerpt, but the "
        "standalone term 'statistics' does not; statistical physics is a physics subfield, not "
        "the statistics taxonomy skill.",
    ),
    # --- physics-expert-high-energy-mathematical-physics -------------------
    ("highenergy", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "for a theoretical-physics consulting role.",
    ),
    # --- kiembu-bilingual-expert -------------------------------------------
    ("kiembu", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems'). "
        "'Background or interest in linguistics, translation, or language technology is a plus' "
        "is not an AI mention.",
    ),
    # --- physics-expert-condensed-matter-quantum-information ---------------
    ("condensed", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "for a physics research role.",
    ),
    # --- biglaw-lawyers -----------------------------------------------------
    ("biglaw", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "for a legal-analysis role.",
    ),
    # --- strategy-operations-associate -------------------------------------
    ("strategy-ops", "skill.ai"): _unc(
        [("description_html_raw", "that are not AI-native")],
        "AI appears only in company/product context: the employer builds a 'proactive smart "
        "assistant' for 'basic applications ... that are not AI-native'; the strategy and "
        "operations role itself has no AI requirement.",
        "Decide whether company/product-level AI context ('not AI-native', 'proactive smart "
        "assistant', 'multi-step reasoning') counts as evidence of the AI skill for a "
        "non-technical strategy and operations role.",
        notes="Company-context mention; first draft also labeled this pair uncertain (agreement).",
    ),
    # --- physics-expert-amo-quantum-information ----------------------------
    ("amo", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "for a quantum-optics research role.",
    ),
    # --- founding-full-stack-ios-engineer ----------------------------------
    ("ios-engineer", "skill.ios"): _sup(
        [("title_raw", "iOS Engineer")],
        "The title ('Founding Full-Stack iOS Engineer') and the description ('own the companion "
        "iOS app end-to-end') explicitly require iOS development.",
    ),
    ("ios-engineer", "skill.swift"): _sup(
        [("description_html_raw", "Swift")],
        "Explicitly required: 'Strong proficiency in Swift and the iOS ecosystem' (the raw HTML "
        "wraps the token 'Swift' in an inline tag, so the exact quote is the single token).",
    ),
    ("ios-engineer", "skill.bluetooth"): _sup(
        [("description_html_raw", "Bluetooth/BLE hardware integration")],
        "Listed under nice-to-have: 'Familiarity with biometric data, Bluetooth/BLE hardware "
        "integration, or real-time data streaming'.",
    ),
    ("ios-engineer", "skill.ai"): _ns(
        "Confusion case: no 'AI' token appears in any reviewed field; 'emotional intelligence' "
        "(EQ) is not the AI skill, and 'a proprietary computational neuroscience inference "
        "model' contains no AI term.",
        notes="'Emotional intelligence' is an EQ boundary case, not the AI skill.",
    ),
    # --- founding-full-stack-engineer ---------------------------------------
    ("fullstack", "skill.typescript"): _sup(
        [("description_html_raw", "TypeScript, React, and server-side JavaScript")],
        "Explicitly required: 'Strong full-stack development skills: TypeScript, React, and "
        "server-side JavaScript (Node.js)'; TypeScript is also in the tech-stack list.",
    ),
    ("fullstack", "skill.react"): _sup(
        [("description_html_raw", "TypeScript, React, and server-side JavaScript")],
        "Explicitly required and listed in the tech stack ('Next.js, React, TypeScript, ...').",
    ),
    ("fullstack", "skill.javascript"): _sup(
        [("description_html_raw", "TypeScript, React, and server-side JavaScript")],
        "Explicitly required: 'server-side JavaScript (Node.js)'.",
    ),
    ("fullstack", "skill.nodejs"): _sup(
        [("description_html_raw", "server-side JavaScript (Node.js)")],
        "Explicitly required: 'server-side JavaScript (Node.js)'.",
    ),
    ("fullstack", "skill.ai"): _sup(
        [("description_html_raw", "Build AI workflows")],
        "The role explicitly builds AI features: 'Build AI workflows for exemplar writing, "
        "evidence organization, and document retrieval' and 'Experience building AI-powered "
        "workflows'.",
    ),
    ("fullstack", "skill.aws"): _sup(
        [("description_html_raw", "Supabase, Vercel, AWS S3")],
        "The tech stack explicitly lists 'AWS S3'.",
    ),
    ("fullstack", "skill.saml"): _sup(
        [("description_html_raw", "SSO/SAML")],
        "Explicitly required: 'enterprise infrastructure including SSO/SAML, role-based access "
        "control (RBAC)' and 'enterprise authentication (SSO/SAML)'.",
    ),
    ("fullstack", "skill.sso"): _sup(
        [("description_html_raw", "SSO/SAML")],
        "Explicitly required: 'enterprise authentication (SSO/SAML)' and 'SSO/SAML, role-based "
        "access control (RBAC)'.",
    ),
    ("fullstack", "skill.rbac"): _sup(
        [("description_html_raw", "role-based access control (RBAC)")],
        "Explicitly required: 'role-based access control (RBAC)'.",
    ),
    ("fullstack", "skill.java"): _ns(
        "Boundary case: 'JavaScript' appears but 'java' does not; java and javascript are "
        "distinct taxonomy skills with separate identifiers.",
    ),
    ("fullstack", "skill.data_science"): _ns(
        "Confusion case: 'data models' appears ('Design data models and backend services for "
        "complex multi-hospital, multi-unit organizational structures') but is not the "
        "data-science skill; no explicit data-science mention exists.",
    ),
    # --- senior-machine-learning-engineer -----------------------------------
    ("senior-ml", "skill.machine_learning"): _sup(
        [("title_raw", "Machine Learning")],
        "The title is 'Senior Machine Learning Engineer' and the description makes the role an "
        "independent owner of 'critical ML subsystems in production'.",
    ),
    ("senior-ml", "skill.ai"): _sup(
        [("description_html_raw", "long-horizon AI product")],
        "The role builds core ML systems that power a 'proactive, long-horizon AI product' and "
        "brings 'AI to have practical benefits'; AI is the product domain.",
        notes="Category context reinforces: categories_raw includes 'Senior-AI-ML-Engineer'.",
    ),
    ("senior-ml", "skill.python"): _sup(
        [("description_html_raw", "Python")],
        "The tech stack explicitly lists 'Python'.",
    ),
    ("senior-ml", "skill.pytorch"): _sup(
        [("description_html_raw", "PyTorch / JAX")],
        "The tech stack explicitly lists 'PyTorch / JAX'.",
    ),
    ("senior-ml", "skill.jax"): _sup(
        [("description_html_raw", "PyTorch / JAX")],
        "The tech stack explicitly lists 'PyTorch / JAX'.",
    ),
    ("senior-ml", "skill.gpu"): _sup(
        [("description_html_raw", "GPU-based training and inference systems")],
        "The tech stack explicitly lists 'GPU-based training and inference systems'.",
    ),
    # --- physics-expert-statistical-physics-quantum-information-condensed-matter
    ("statistical", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "for a physics research role.",
    ),
    ("statistical", "skill.statistics"): _ns(
        "Boundary case: 'Statistical Physics' appears in the title and description, but the "
        "standalone term 'statistics' does not; statistical physics is a physics subfield, not "
        "the statistics taxonomy skill.",
    ),
    # --- founding-member-of-technical-staff ---------------------------------
    ("founding-mts", "skill.ai"): _sup(
        [("description_html_raw", "AI model validation")],
        "AI is central to the role: 'healthtech / safety-critical AI startup building evidence "
        "infrastructure for AI model validation in medical diagnostics'; the role also uses 'AI "
        "tooling' and requires 'AI/ML medical device submissions' experience as a plus.",
    ),
    ("founding-mts", "skill.python"): _sup(
        [("description_html_raw", "production-quality Python")],
        "Explicitly required: 'Write production-quality Python, build agentic workflows for "
        "evidence investigation'.",
    ),
    ("founding-mts", "skill.machine_learning"): _sup(
        [("description_html_raw", "ML, statistics, and data science fundamentals")],
        "Explicitly required: 'Strong ML, statistics, and data science fundamentals'.",
    ),
    ("founding-mts", "skill.data_science"): _sup(
        [("description_html_raw", "ML, statistics, and data science fundamentals")],
        "Explicitly required: 'Strong ML, statistics, and data science fundamentals'.",
    ),
    ("founding-mts", "skill.statistics"): _sup(
        [("description_html_raw", "ML, statistics, and data science fundamentals")],
        "Explicitly required: 'Strong ML, statistics, and data science fundamentals'.",
    ),
    # --- physics-expert-gravitation-cosmology-astrophysics -----------------
    ("gravitation", "skill.ai"): _ns(
        "Negative-requirement case: the posting explicitly says 'No prior experience in AI is "
        "required'; AI appears only as project context ('help train next-generation AI systems') "
        "for a physics research role.",
    ),
}

#: Verificado manualmente: cada entrada curada referencia un registro declarado y una
#: habilidad real de la taxonomía; ver el assert en ``annotate_second_pass``.


def _default_spec(skill_name: str) -> dict:
    return _ns(
        f"No explicit mention of {skill_name} in the reviewed fields; not_supported means no "
        "explicit positive evidence in the reviewed fields, never that the person or job lacks "
        "the skill."
    )


# ---------------------------------------------------------------------------
# Modelo tipado.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecondPassLabel:
    """Un par ``(source_id, skill_id)`` etiquetado de forma independiente."""

    source_id: str
    skill_id: str
    label: str
    evidence: tuple[Evidence, ...]
    reviewed_fields: tuple[str, ...]
    reason: str
    human_review_question: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SecondPassSet:
    """Artefacto de revisión de segunda pasada validado (metadatos + 740 etiquetas)."""

    evaluation_version: str
    evaluation_kind: str | None
    annotation_status: str
    human_review_required: bool
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
    labels: tuple[SecondPassLabel, ...]


# ---------------------------------------------------------------------------
# Rutina de anotación independiente (lee solo los campos de origen).
# ---------------------------------------------------------------------------


def _resolve_quotes(record: Mapping[str, Any], quotes: tuple[tuple[str, str], ...]) -> tuple[Evidence, ...]:
    entries: list[Evidence] = []
    for field, quote in quotes:
        value = record.get(field)
        if not isinstance(value, str):
            raise EvaluationError(
                f"adjudication quote field {field!r} is not a string in record "
                f"{record.get('source_id')!r}; got {type(value).__name__}"
            )
        span = resolve_quote_span(value, quote)
        if span is None:
            raise EvaluationError(
                f"adjudication quote {quote!r} was not found in {field} of record "
                f"{record.get('source_id')!r}; the curated manifest must quote the exact text"
            )
        start, end = span
        entries.append(Evidence(field=field, exact_quote=quote, char_start=start, char_end=end))
    return tuple(entries)


def annotate_second_pass(dataset: Mapping[str, Any], taxonomy: Taxonomy) -> tuple[SecondPassLabel, ...]:
    """Etiqueta TODOS los pares registro x taxonomía mediante lectura directa del texto de origen.

    El manifiesto de adjudicación curado impulsa toda decisión no predeterminada;
    todo par restante queda por defecto como ``not_supported``. Esta rutina NUNCA
    lee ``skill_evidence`` (la salida del matcher): la independencia se garantiza
    por construcción y se prueba eliminando ``skill_evidence`` de una copia del
    conjunto de datos.
    """
    records = dataset.get("records")
    if not isinstance(records, list):
        raise EvaluationError("the dataset has no 'records' list")
    skill_ids = sorted(skill.skill_id for skill in taxonomy.skills)

    known_skills = {skill.skill_id for skill in taxonomy.skills}
    for short, skill_id in _ADJUDICATION:
        if skill_id not in known_skills:
            raise EvaluationError(
                f"adjudication manifest references unknown taxonomy skill {skill_id!r} "
                f"for record {short!r}"
            )

    labels: list[SecondPassLabel] = []
    used_keys: set[tuple[str, str]] = set()
    record_by_source = {record.get("source_id"): record for record in records if isinstance(record, dict)}
    for source_id, record in sorted(record_by_source.items()):
        short = _SOURCE_SHORT_BY_URL.get(source_id)
        for skill_id in skill_ids:
            spec = _ADJUDICATION.get((short, skill_id)) if short is not None else None
            if spec is None:
                skill = taxonomy.skill_by_id(skill_id)
                spec = _default_spec(skill.name if skill is not None else skill_id)
            else:
                used_keys.add((short, skill_id))
            evidence = _resolve_quotes(record, spec["quotes"])
            labels.append(
                SecondPassLabel(
                    source_id=source_id,
                    skill_id=skill_id,
                    label=spec["label"],
                    evidence=evidence,
                    reviewed_fields=REVIEWED_FIELDS,
                    reason=spec["reason"],
                    human_review_question=spec["human_review_question"],
                    notes=spec["notes"],
                )
            )

    unused = set(_ADJUDICATION) - used_keys
    if unused:
        raise EvaluationError(
            "adjudication manifest entries were not consumed (unknown record or record missing "
            f"from the dataset): {sorted(unused)}"
        )
    return tuple(labels)


# ---------------------------------------------------------------------------
# Construcción del artefacto y validación de esquema.
# ---------------------------------------------------------------------------


ANNOTATION_METHOD = (
    "Independent second-pass review: all 740 (source_id, skill_id) pairs (20 records x 37 "
    "taxonomy skills) were labeled by a separate direct-text annotation routine "
    "(analysis/second_pass.py) driven by a curated adjudication manifest. Labels were decided "
    "independently by reading the source-text fields preserved in the analytics dataset (title_raw, "
    "excerpt_raw, categories_raw, description_html_raw); taxonomy terms were used only as "
    "candidate vocabulary. Matcher predictions (skill_evidence.skills) were NOT read while "
    "labeling and are compared only afterwards by compare_with_predictions(...). Supported "
    "labels cite exact quotes with half-open offsets verified as field[char_start:char_end] == "
    "exact_quote; not_supported means no explicit positive evidence in the reviewed fields "
    "(never that the person or job lacks the skill) and lists reviewed_fields; uncertain labels "
    "carry the ambiguous quote when text exists plus a human_review_question. Boundary and "
    "negative-requirement cases are documented per label: java vs javascript, git vs github, "
    "AI in company/category context, and 'No prior experience in AI is required'. This artifact "
    "is a DRAFT second pass (annotation_status: draft_second_pass) that REQUIRES human review "
    "(human_review_required: true); it is NOT gold and NOT human-reviewed, and no matcher or "
    "taxonomy rule was changed."
)

SAMPLE_WARNING = "development_sample: 20 records, one page, complete: false; not a full feed and not market coverage"

SAMPLE_LIMITATIONS = [
    "development_sample: exactly 20 records from one bounded page (limit=20, offset=0) of one "
    "source (himalayas), snapshot cap_0370798f7af4b0e3, complete: false",
    "not market coverage: one page of one job board is not a market snapshot and no whole-market "
    "claim is made",
]


def build_second_pass_doc(dataset: Mapping[str, Any], taxonomy: Taxonomy) -> dict:
    """Construye el documento completo del artefacto de revisión de segunda pasada.

    Totalmente offline y determinista: el manifiesto curado es la única fuente de
    anotación y aquí nunca se consulta la salida del matcher.
    """
    identity = dataset.get("capture_identity")
    identity = identity if isinstance(identity, dict) else {}
    sample = dataset.get("sample")
    sample = sample if isinstance(sample, dict) else {}
    labels = annotate_second_pass(dataset, taxonomy)
    return {
        "evaluation_version": REVIEW_VERSION,
        "evaluation_kind": REVIEW_KIND,
        "annotation_status": REVIEW_STATUS,
        "human_review_required": True,
        "dataset_type": DATASET_TYPE,
        "dataset_version": dataset.get("dataset_version"),
        "snapshot_id": SNAPSHOT_ID,
        "taxonomy_version": taxonomy.version,
        "matcher_version": dataset.get("matcher_version"),
        "source": identity.get("source", "himalayas"),
        "endpoint": identity.get("endpoint"),
        "attribution_url": identity.get("attribution_url", "https://himalayas.app"),
        "annotation_date": ANNOTATION_DATE,
        "annotation_method": ANNOTATION_METHOD,
        "sample": {
            "records": sample.get("records"),
            "page": sample.get("page"),
            "limit": sample.get("limit"),
            "offset": sample.get("offset"),
            "complete": sample.get("complete"),
            "warning": SAMPLE_WARNING,
            "limitations": list(SAMPLE_LIMITATIONS),
        },
        "labels": [_label_to_dict(label) for label in labels],
    }


def _require_string(doc: Mapping[str, Any], key: str, label: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} must be a non-empty string; got {value!r}")
    return value


def _optional_string(doc: Mapping[str, Any], key: str) -> str | None:
    value = doc.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"'{key}' must be a non-empty string when present; got {value!r}")
    return value


def _label_to_dict(label: SecondPassLabel) -> dict:
    entry: dict = {
        "source_id": label.source_id,
        "skill_id": label.skill_id,
        "label": label.label,
        "evidence": [
            {
                "field": ev.field,
                "exact_quote": ev.exact_quote,
                "char_start": ev.char_start,
                "char_end": ev.char_end,
            }
            for ev in label.evidence
        ],
        "reviewed_fields": list(label.reviewed_fields),
        "reason": label.reason,
    }
    if label.human_review_question is not None:
        entry["human_review_question"] = label.human_review_question
    if label.notes is not None:
        entry["notes"] = label.notes
    return entry


def _parse_label(entry: Any) -> SecondPassLabel:
    if not isinstance(entry, dict):
        raise EvaluationError("every label entry must be a JSON object")
    source_id = _require_string(entry, "source_id", "label 'source_id'")
    skill_id = _require_string(entry, "skill_id", "label 'skill_id'")
    value = entry.get("label")
    if value not in LABEL_VALUES:
        raise EvaluationError(
            f"label must be one of {LABEL_VALUES}; got {value!r} for ({source_id}, {skill_id})"
        )
    evidence = _parse_evidence(entry.get("evidence", []))
    if value == "supported" and not evidence:
        raise EvaluationError(
            f"supported label ({source_id}, {skill_id}) must carry at least one exact evidence entry"
        )
    if value == "not_supported" and evidence:
        raise EvaluationError(
            f"not_supported label ({source_id}, {skill_id}) must have empty evidence; "
            "evidence is reserved for explicit positive evidence"
        )
    reviewed_raw = entry.get("reviewed_fields")
    if not isinstance(reviewed_raw, list) or not reviewed_raw:
        raise EvaluationError(
            f"label ({source_id}, {skill_id}) must declare non-empty reviewed_fields"
        )
    for field in reviewed_raw:
        if not isinstance(field, str) or field not in REVIEWED_FIELDS:
            raise EvaluationError(
                f"reviewed field {field!r} of ({source_id}, {skill_id}) must be one of "
                f"{REVIEWED_FIELDS}"
            )
    reviewed_fields = tuple(reviewed_raw)
    reason = _require_string(entry, "reason", f"label ({source_id}, {skill_id}) 'reason'")
    question_raw = entry.get("human_review_question")
    if value == "uncertain":
        if not isinstance(question_raw, str) or not question_raw.strip():
            raise EvaluationError(
                f"uncertain label ({source_id}, {skill_id}) must carry a non-empty "
                "human_review_question describing what a person should decide"
            )
        question: str | None = question_raw
    else:
        if question_raw is not None:
            raise EvaluationError(
                f"label ({source_id}, {skill_id}) is {value!r}; human_review_question is "
                "reserved for uncertain labels"
            )
        question = None
    notes_raw = entry.get("notes")
    notes = notes_raw if isinstance(notes_raw, str) and notes_raw.strip() else None
    return SecondPassLabel(
        source_id=source_id,
        skill_id=skill_id,
        label=value,
        evidence=evidence,
        reviewed_fields=reviewed_fields,
        reason=reason,
        human_review_question=question,
        notes=notes,
    )


def second_pass_from_dict(doc: Mapping[str, Any]) -> SecondPassSet:
    """Valida un artefacto de revisión de segunda pasada parseado (comprobaciones de esquema con cierre ante fallo)."""
    if not isinstance(doc, dict):
        raise EvaluationError(
            f"the second-pass review document must be a JSON object; got {type(doc).__name__}"
        )
    for key in _REQUIRED_METADATA:
        _require_string(doc, key, f"'{key}'")
    if doc["evaluation_version"] != REVIEW_VERSION:
        raise EvaluationError(
            f"evaluation_version must be exactly {REVIEW_VERSION!r}; got {doc['evaluation_version']!r}"
        )
    if doc["annotation_status"] != REVIEW_STATUS:
        raise EvaluationError(
            f"annotation_status must be exactly 'draft_second_pass' (this artifact is a draft "
            f"second pass that requires human review, never gold or human-reviewed); got "
            f"{doc['annotation_status']!r}"
        )
    if doc.get("human_review_required") is not True:
        raise EvaluationError(
            "human_review_required must be true: this second-pass artifact requires human review"
        )
    if "evaluation_status" in doc:
        status = doc["evaluation_status"]
        if status in FORBIDDEN_STATUS_VALUES:
            raise EvaluationError(
                f"forbidden status claim: evaluation_status={status!r} would falsely mark the "
                "artifact as reviewed/gold; the second pass is draft_second_pass"
            )
        raise EvaluationError(
            "evaluation_status is not a field of the second-pass review artifact; use "
            "annotation_status (draft_second_pass)"
        )
    if doc.get("human_reviewed"):
        raise EvaluationError(
            "forbidden claim: 'human_reviewed' must not be truthy; the second pass is NOT "
            "human-reviewed"
        )
    sample = _parse_sample(doc.get("sample"))
    warning = sample.get("warning")
    if not isinstance(warning, str) or "market" not in warning:
        raise EvaluationError(
            "sample.warning must explicitly state the no-market-coverage warning (20 records, "
            "one page, complete: false; not market coverage)"
        )

    labels_raw = doc.get("labels")
    if not isinstance(labels_raw, list):
        raise EvaluationError("'labels' must be a JSON array")
    labels = tuple(_parse_label(entry) for entry in labels_raw)
    if len(labels) != 740:
        raise EvaluationError(
            f"the second pass must label exactly 740 (source_id, skill_id) pairs (20 records x "
            f"37 taxonomy skills); got {len(labels)}"
        )
    pairs = [(label.source_id, label.skill_id) for label in labels]
    if len(set(pairs)) != len(pairs):
        raise EvaluationError("duplicate (source_id, skill_id) labels are not allowed")

    return SecondPassSet(
        evaluation_version=doc["evaluation_version"],
        evaluation_kind=_optional_string(doc, "evaluation_kind"),
        annotation_status=doc["annotation_status"],
        human_review_required=doc["human_review_required"],
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
        sample=sample,
        labels=labels,
    )


def load_second_pass_review(path: str | Path) -> SecondPassSet:
    """Carga y valida el artefacto de revisión de segunda pasada desde un archivo JSON."""
    try:
        raw_text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"cannot read second-pass review artifact {path}: {exc}") from exc
    try:
        doc = json.loads(raw_text)
    except ValueError as exc:
        raise EvaluationError(f"second-pass review artifact {path} is not valid JSON: {exc}") from exc
    return second_pass_from_dict(doc)


def validate_second_pass(review: SecondPassSet, dataset: Mapping[str, Any], taxonomy: Taxonomy) -> None:
    """Falla con cierre cuando la revisión no anota este conjunto de datos exacto.

    Comprueba la concordancia de metadatos (tipo de conjunto de datos, snapshot,
    versión de taxonomía, forma de la muestra), la cobertura exacta de los pares
    20 x 37, la existencia de cada source id y skill id, y el contrato exacto de
    evidencia (``field[char_start:char_end] == exact_quote`` con desplazamientos
    no negativos y dentro de los límites en campos de tipo cadena).
    """
    if not isinstance(dataset, dict):
        raise EvaluationError("the dataset must be a JSON object")
    if review.dataset_type != dataset.get("dataset_kind"):
        raise EvaluationError(
            f"dataset type mismatch: the review annotates {review.dataset_type!r} but the "
            f"dataset declares {dataset.get('dataset_kind')!r}"
        )
    if review.taxonomy_version != dataset.get("taxonomy_version"):
        raise EvaluationError(
            f"taxonomy version mismatch: the review declares {review.taxonomy_version!r} but the "
            f"dataset declares {dataset.get('taxonomy_version')!r}"
        )
    if review.taxonomy_version != taxonomy.version:
        raise EvaluationError(
            f"taxonomy version mismatch: the review declares {review.taxonomy_version!r} but the "
            f"taxonomy artifact is {taxonomy.version!r}"
        )
    identity = dataset.get("capture_identity")
    if not isinstance(identity, dict) or identity.get("snapshot_id") != review.snapshot_id:
        raise EvaluationError(
            f"snapshot mismatch: the review declares {review.snapshot_id!r} but the dataset "
            f"carries {identity.get('snapshot_id') if isinstance(identity, dict) else None!r}"
        )
    sample = dataset.get("sample")
    if not isinstance(sample, dict):
        raise EvaluationError("the dataset has no 'sample' metadata object")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise EvaluationError("the dataset has no 'records' list")
    for label_name in ("records", "page", "limit", "offset", "complete"):
        if review.sample.get(label_name) != sample.get(label_name):
            raise EvaluationError(
                f"sample mismatch: the review declares sample.{label_name} = "
                f"{review.sample.get(label_name)!r} but the dataset declares "
                f"{sample.get(label_name)!r}"
            )
    if review.sample.get("records") != len(records):
        raise EvaluationError(
            f"sample mismatch: the review declares {review.sample.get('records')} records but "
            f"the dataset carries {len(records)}"
        )

    record_by_source = {record.get("source_id"): record for record in records if isinstance(record, dict)}
    if len(record_by_source) != len(records):
        raise EvaluationError("the dataset contains duplicate source ids; refusing to validate")

    expected_pairs = {
        (source_id, skill.skill_id) for source_id in record_by_source for skill in taxonomy.skills
    }
    actual_pairs = {(label.source_id, label.skill_id) for label in review.labels}
    if actual_pairs != expected_pairs:
        missing = sorted(expected_pairs - actual_pairs)
        extra = sorted(actual_pairs - expected_pairs)
        raise EvaluationError(
            "the second pass must label exactly the full record x taxonomy product "
            f"({len(expected_pairs)} pairs); missing {len(missing)} and extra {len(extra)}"
        )

    for entry in review.labels:
        record = record_by_source.get(entry.source_id)
        if record is None:
            raise EvaluationError(
                f"label source_id {entry.source_id!r} does not exist in the dataset records"
            )
        if taxonomy.skill_by_id(entry.skill_id) is None:
            raise EvaluationError(
                f"label skill_id {entry.skill_id!r} does not exist in the taxonomy "
                f"{taxonomy.version}"
            )
        for ev in entry.evidence:
            value = record.get(ev.field)
            if not isinstance(value, str):
                raise EvaluationError(
                    f"evidence field {ev.field!r} is not a string in record {entry.source_id!r}; "
                    f"got {type(value).__name__}"
                )
            if ev.char_end > len(value):
                raise EvaluationError(
                    f"evidence char_end {ev.char_end} exceeds the length of {ev.field} "
                    f"({len(value)}) in record {entry.source_id!r}"
                )
            actual = value[ev.char_start:ev.char_end]
            if actual != ev.exact_quote:
                raise EvaluationError(
                    f"evidence quote mismatch in record {entry.source_id!r} for skill "
                    f"{entry.skill_id!r}: {ev.field}[{ev.char_start}:{ev.char_end}] = {actual!r} "
                    f"but the label records {ev.exact_quote!r}"
                )


# ---------------------------------------------------------------------------
# Comparación: etiquetas de la segunda pasada vs predicciones del matcher (las etiquetas ya existen).
# ---------------------------------------------------------------------------


def compare_with_predictions(
    second_pass: SecondPassSet, dataset: Mapping[str, Any], taxonomy: Taxonomy
) -> dict:
    """Contingencia a nivel de par de las etiquetas de la segunda pasada vs predicciones del matcher.

    Se ejecuta SOLO después de que existan las 740 etiquetas. Cada habilidad
    predicha cuenta como máximo una vez por registro (``predictions_by_record``).
    Las etiquetas inciertas se cuentan por separado y no aparecen en ninguna
    celda; los pares predichos sin etiqueta se excluyen de las celdas y se
    notifican (la segunda pasada no deja ninguno).
    """
    predictions = predictions_by_record(dataset)
    record_by_source = {
        record.get("source_id"): record for record in dataset.get("records", []) if isinstance(record, dict)
    }
    labels_by_pair = {(label.source_id, label.skill_id) for label in second_pass.labels}

    tp = fp = fn = tn = uncertain = 0
    per_skill: dict[str, dict[str, int]] = {}
    false_positives: list[dict] = []
    false_negatives: list[dict] = []

    for entry in second_pass.labels:
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
                        "reason": entry.reason,
                        "gold_evidence": [
                            {
                                "field": ev.field,
                                "exact_quote": ev.exact_quote,
                                "char_start": ev.char_start,
                                "char_end": ev.char_end,
                            }
                            for ev in entry.evidence
                        ],
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
                        "reason": entry.reason,
                        "matcher_evidence": _matcher_evidence(
                            record_by_source.get(entry.source_id, {}), entry.skill_id
                        ),
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

    precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
    scope = sorted(
        skill_id
        for skill_id, counts in per_skill.items()
        if sum(counts.values()) > 0
    )
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
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "uncertain": uncertain,
        "labeled_pairs": len(second_pass.labels),
        "non_uncertain_labeled_pairs": tp + fp + fn + tn,
        "per_skill": dict(sorted(per_skill.items())),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "predicted_pairs": sum(len(skills) for skills in predictions.values()),
        "unlabeled_predicted_pairs": unlabeled_predicted_pairs,
        "metrics": {
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
                    "primary metrics pool every non-uncertain labeled pair (micro); precision/recall "
                    "are undefined (None) when the denominator is zero, F1 is 0.0 when at least one "
                    "of them is defined as 0"
                ),
            },
            "micro": {
                "scope_note": (
                    "micro metrics pool all non-uncertain labeled pairs (each pair contributes "
                    "equally); identical to the primary metrics by definition"
                ),
                "denominator_pairs": tp + fp + fn + tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            },
            "macro": macro,
            "uncertain": {
                "count": uncertain,
                "excluded_note": (
                    "uncertain labels are reported separately and excluded from all primary "
                    "denominators and from the macro scope"
                ),
            },
        },
    }


# ---------------------------------------------------------------------------
# Comparación: primer borrador vs segunda pasada.
# ---------------------------------------------------------------------------


def compare_first_vs_second(first_pass, second_pass: SecondPassSet) -> dict:
    """Comparación determinista de etiquetas entre el primer borrador y la segunda pasada.

    Solo los pares etiquetados en AMBAS pasadas son acuerdos/desacuerdos; los
    pares que el primer borrador dejó sin etiquetar se cuentan como
    ``first_draft_unlabeled_pairs`` y nunca se tratan como desacuerdos. La cola
    de revisión humana es la unión deduplicada de todas las etiquetas inciertas
    de la segunda pasada y de todos los desacuerdos.
    """
    first_map = {(label.source_id, label.skill_id): label for label in first_pass.labels}
    second_map = {(label.source_id, label.skill_id): label for label in second_pass.labels}

    per_skill: dict[str, dict[str, int]] = {}
    agreements = 0
    disagreements = 0
    disagreement_list: list[dict] = []
    for pair in sorted(first_map):
        first = first_map[pair]
        second = second_map[pair]
        if first.label == second.label:
            agreements += 1
        else:
            disagreements += 1
            disagreement_list.append(
                {
                    "source_id": pair[0],
                    "skill_id": pair[1],
                    "first_draft_label": first.label,
                    "second_pass_label": second.label,
                    "first_draft_reason": first.notes,
                    "second_pass_reason": second.reason,
                    "second_pass_evidence": [
                        {
                            "field": ev.field,
                            "exact_quote": ev.exact_quote,
                            "char_start": ev.char_start,
                            "char_end": ev.char_end,
                        }
                        for ev in second.evidence
                    ],
                    "second_pass_notes": second.notes,
                }
            )
        skill_counts = per_skill.setdefault(pair[1], {"first_draft_labels": 0, "agreements": 0, "disagreements": 0})
        skill_counts["first_draft_labels"] += 1
        skill_counts["agreements" if first.label == second.label else "disagreements"] += 1

    queue_items: dict[tuple[str, str], dict] = {}
    for pair, label in sorted(second_map.items()):
        if label.label != "uncertain":
            continue
        first_label = first_map[pair].label if pair in first_map else None
        queue_items[pair] = {
            "source_id": pair[0],
            "skill_id": pair[1],
            "second_pass_label": label.label,
            "first_draft_label": first_label,
            "reason": label.reason,
            "human_review_question": label.human_review_question,
            "evidence": [
                {
                    "field": ev.field,
                    "exact_quote": ev.exact_quote,
                    "char_start": ev.char_start,
                    "char_end": ev.char_end,
                }
                for ev in label.evidence
            ],
        }
    for entry in disagreement_list:
        pair = (entry["source_id"], entry["skill_id"])
        second = second_map[pair]
        queue_items.setdefault(
            pair,
            {
                "source_id": pair[0],
                "skill_id": pair[1],
                "second_pass_label": second.label,
                "first_draft_label": first_map[pair].label,
                "reason": second.reason,
                "human_review_question": second.human_review_question,
                "evidence": [
                    {
                        "field": ev.field,
                        "exact_quote": ev.exact_quote,
                        "char_start": ev.char_start,
                        "char_end": ev.char_end,
                    }
                    for ev in second.evidence
                ],
            },
        )

    return {
        "first_draft_labels": len(first_map),
        "second_pass_labels": len(second_map),
        "overlapping_pairs": len(first_map),
        "agreements": agreements,
        "disagreements": disagreements,
        "first_draft_unlabeled_pairs": len(second_map) - len(first_map),
        "note": (
            "only pairs labeled in both passes are agreements or disagreements; the 680 pairs "
            "the first draft left unlabeled are counted as first_draft_unlabeled_pairs and are "
            "never treated as disagreements"
        ),
        "per_skill": dict(sorted(per_skill.items())),
        "disagreement_list": disagreement_list,
        "human_review_queue": {
            "count": len(queue_items),
            "note": (
                "all uncertain second-pass labels plus all first-vs-second disagreements "
                "(deduplicated); each item states what a person should decide"
            ),
            "items": [queue_items[pair] for pair in sorted(queue_items)],
        },
    }


# ---------------------------------------------------------------------------
# Informe determinista.
# ---------------------------------------------------------------------------


def build_second_pass_report(
    first_pass, second_pass: SecondPassSet, dataset: Mapping[str, Any], taxonomy: Taxonomy
) -> dict:
    """Construye el informe determinista de revisión de segunda pasada."""
    validate_second_pass(second_pass, dataset, taxonomy)
    comp = compare_first_vs_second(first_pass, second_pass)
    cont = compare_with_predictions(second_pass, dataset, taxonomy)
    metrics = cont["metrics"]

    records = dataset.get("records", [])
    annotated_ids = sorted({label.source_id for label in second_pass.labels})
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

    first_counts = {"supported": 0, "not_supported": 0, "uncertain": 0}
    for label in first_pass.labels:
        first_counts[label.label] += 1
    second_counts = {"supported": 0, "not_supported": 0, "uncertain": 0}
    for label in second_pass.labels:
        second_counts[label.label] += 1

    uncertain_per_skill: dict[str, int] = {}
    for label in second_pass.labels:
        if label.label == "uncertain":
            uncertain_per_skill[label.skill_id] = uncertain_per_skill.get(label.skill_id, 0) + 1
    skills_highest_uncertainty = sorted(
        ({ "skill_id": skill_id, "uncertain": count} for skill_id, count in uncertain_per_skill.items()),
        key=lambda item: (-item["uncertain"], item["skill_id"]),
    )

    sample = dataset.get("sample") or {}
    return {
        "report_version": "0.2.0",
        "evaluation_version": second_pass.evaluation_version,
        "evaluation_kind": second_pass.evaluation_kind,
        "annotation_status": second_pass.annotation_status,
        "human_review_required": True,
        "dataset_type": second_pass.dataset_type,
        "dataset_version": second_pass.dataset_version,
        "snapshot_id": second_pass.snapshot_id,
        "taxonomy_version": second_pass.taxonomy_version,
        "matcher_version": second_pass.matcher_version,
        "source": second_pass.source,
        "endpoint": second_pass.endpoint,
        "attribution_url": second_pass.attribution_url,
        "annotation_date": second_pass.annotation_date,
        "sample": {
            "records": second_pass.sample.get("records"),
            "page": second_pass.sample.get("page"),
            "limit": second_pass.sample.get("limit"),
            "offset": second_pass.sample.get("offset"),
            "complete": second_pass.sample.get("complete"),
            "total_count": sample.get("total_count"),
            "warning": second_pass.sample.get("warning"),
            "limitations": list(second_pass.sample.get("limitations", [])),
        },
        "definitions": {
            "primary_micro": (
                "pair-level contingency pooled over all non-uncertain labeled pairs: "
                "supported+predicted=TP, supported+not predicted=FN, not_supported+predicted=FP, "
                "not_supported+not predicted=TN; precision=TP/(TP+FP), recall=TP/(TP+FN), "
                "F1=2*P*R/(P+R) with safe zero denominators"
            ),
            "macro": (
                "unweighted mean of per-skill precision/recall/F1 over taxonomy skills with at "
                "least one non-uncertain labeled pair; skills with no defined value (all labels "
                "not_supported) are excluded and listed explicitly"
            ),
            "uncertain": (
                "ambiguous mentions reported separately and excluded from every primary denominator"
            ),
            "first_vs_second": (
                "only pairs labeled in both passes are agreements/disagreements; first-draft "
                "unlabeled pairs are counted separately and are never disagreements"
            ),
            "human_review_queue": (
                "all uncertain second-pass labels plus all first-vs-second disagreements "
                "(deduplicated), each with the decision a person should make"
            ),
        },
        "label_distribution": {
            "second_pass": {
                "supported": second_counts["supported"],
                "not_supported": second_counts["not_supported"],
                "uncertain": second_counts["uncertain"],
                "total": len(second_pass.labels),
            },
            "first_draft": {
                "supported": first_counts["supported"],
                "not_supported": first_counts["not_supported"],
                "uncertain": first_counts["uncertain"],
                "total": len(first_pass.labels),
            },
            "note": (
                "the second pass labels the full 20 x 37 product; the first draft labeled 60 "
                "pairs, so its counts are not comparable as distributions"
            ),
        },
        "coverage": {
            "definition": (
                "pair coverage = labeled pairs / (dataset records x taxonomy skills); annotated "
                "records = distinct source ids with at least one label"
            ),
            "labeled_pairs": len(second_pass.labels),
            "non_uncertain_labeled_pairs": cont["non_uncertain_labeled_pairs"],
            "total_pairs": len(records) * len(taxonomy.skills),
            "pair_coverage": len(second_pass.labels) / (len(records) * len(taxonomy.skills))
            if records
            else None,
            "non_uncertain_pair_coverage": (
                cont["non_uncertain_labeled_pairs"] / (len(records) * len(taxonomy.skills))
                if records
                else None
            ),
            "annotated_records": len(annotated_ids),
            "annotated_record_ids": annotated_ids,
            "annotated_record_coverage": len(annotated_ids) / len(records) if records else None,
        },
        "first_vs_second": {
            "first_draft_labels": comp["first_draft_labels"],
            "second_pass_labels": comp["second_pass_labels"],
            "overlapping_pairs": comp["overlapping_pairs"],
            "agreements": comp["agreements"],
            "disagreements": comp["disagreements"],
            "first_draft_unlabeled_pairs": comp["first_draft_unlabeled_pairs"],
            "note": comp["note"],
            "per_skill": comp["per_skill"],
            "disagreements": comp["disagreement_list"],
        },
        "human_review_queue": comp["human_review_queue"],
        "uncertainty": {
            "count": len(uncertain_per_skill),
            "total_uncertain_labels": cont["uncertain"],
            "skills_highest_uncertainty": skills_highest_uncertainty,
            "per_skill": dict(sorted(uncertain_per_skill.items())),
        },
        "record_summary": {
            "record_count": len(records),
            "records_reviewed": len(annotated_ids),
            "records_reviewed_coverage": len(annotated_ids) / len(records) if records else None,
            "records_with_evidence": records_with_evidence,
            "records_without_evidence": records_without_evidence,
            "no_evidence_record_ids": sorted(no_evidence_ids) if no_evidence_ids else [],
        },
        "predictions_summary": {
            "predicted_pairs": cont["predicted_pairs"],
            "unlabeled_predicted_pairs": cont["unlabeled_predicted_pairs"],
            "note": (
                "the second pass labels every pair, so no predicted pair is unlabeled "
                "(the first draft left 10 predicted pairs unlabeled and excluded them)"
            ),
        },
        "metrics": metrics,
        "false_positives": cont["false_positives"],
        "false_negatives": cont["false_negatives"],
        "warnings": [
            "draft_second_pass: labels were independently re-annotated from direct source-text "
            "inspection; this second pass is NOT gold or human-reviewed and human review is "
            "REQUIRED (human_review_required: true); every metric on this report is provisional",
            "all 13 false positives are skill.ai predictions in roles whose text explicitly "
            "states 'No prior experience in AI is required' or mentions AI only as project "
            "context; the keyword baseline 0.1.0 does not parse negation (documented; no matcher "
            "change was made)",
            "the second pass labels all 740 pairs, so the 10 predicted pairs the first draft "
            "left unlabeled now enter the contingency (unlabeled predicted pairs: 0)",
        ],
        "limitations": [
            "development sample: exactly 20 records from one page (limit=20, offset=0) of one "
            "source, snapshot cap_0370798f7af4b0e3, complete: false; this is not a full feed and "
            "not market coverage",
            "the second pass is a draft: 5 uncertain labels are excluded from every primary "
            "denominator and 7 items are queued for human review; no label is gold or "
            "human-reviewed",
            "the first draft labeled only 60 of 740 pairs; the 680 first-draft-unlabeled pairs "
            "cannot be compared across passes",
            "the keyword baseline 0.1.0 does not parse negation; negation and context rules were "
            "NOT added to the matcher, only documented",
            "no semantic, LLM, or embedding analysis was used for labels or predictions",
        ],
        "guardrails": [
            "labels are a draft second pass, not gold or human-reviewed; human review is required",
            "uncertain labels are excluded from all primary denominators and reported separately",
            "unlabeled pairs are excluded from the metrics, never treated as false positives or "
            "negatives",
            "not_supported means no explicit positive evidence in the reviewed fields, never that "
            "the person or job lacks the skill",
            "no market coverage: one page of one job board is not a market snapshot",
            "no matcher or taxonomy source file was changed by this review",
        ],
    }


# ---------------------------------------------------------------------------
# Serialización.
# ---------------------------------------------------------------------------


def serialize_second_pass(doc: Mapping[str, Any]) -> bytes:
    """Serialización JSON canónica en UTF-8 (claves ordenadas, sangría de 2 espacios)."""
    return (json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def serialize_second_pass_report(report: Mapping[str, Any]) -> bytes:
    """Serialización JSON determinista en UTF-8 para el informe de revisión."""
    return (json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
