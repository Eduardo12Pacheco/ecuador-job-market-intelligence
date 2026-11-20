"""Herramientas analíticas offline: taxonomía versionada, línea base
determinista de palabras clave, conjunto de datos canónico de desarrollo,
informe de calidad, análisis descriptivo y visualizaciones de línea base.

Todo aquí es solo biblioteca estándar, determinista y totalmente offline:
sin LLMs, embeddings, búsqueda semántica, inferencia difusa, servicios cloud
ni acceso a red. El artefacto de taxonomía bajo ``data/taxonomy/`` es la
fuente de verdad de las reglas de coincidencia; el conjunto de datos de
desarrollo materializado vive bajo ``data/analytics/`` y se puede regenerar
con::

    uv run python -m job_market_intelligence.analysis.materialize

El artefacto de análisis descriptivo y las visualizaciones de línea base se
regeneran con::

    uv run python -m job_market_intelligence.analysis.visualize

El conjunto de evaluación de borrador de extracción de habilidades vive bajo
``data/evaluation/`` y su informe se regenera con::

    uv run python -m job_market_intelligence.analysis.evaluate

Ver ``docs/ingestion/himalayas-adapter-contract.md`` y el README para la
identidad de captura de la que se derivan estos artefactos.
"""

from .dataset import (
    DATASET_KIND,
    DATASET_VERSION,
    build_development_dataset,
    resolve_snapshot_id,
    serialize_dataset,
)
from .descriptive import (
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
from .errors import (
    AnalysisError,
    DatasetError,
    DatasetIntegrityError,
    DescriptiveError,
    EvaluationError,
    TaxonomyError,
)
from .evaluation import (
    ANNOTATION_DATE,
    DATASET_TYPE,
    EVALUATION_ARTIFACT_DEFAULT_PATH,
    EVALUATION_KIND,
    EVALUATION_STATUS,
    EVALUATION_VERSION,
    EVIDENCE_FIELDS,
    LABEL_VALUES,
    REPORT_ARTIFACT_DEFAULT_PATH,
    TAXONOMY_VERSION,
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
from .matcher import (
    EXCERPT_CONTEXT_CHARS,
    MATCHER_VERSION,
    SEARCHED_FIELDS,
    JobSkillResult,
    SkillMatch,
    field_text,
    match_job,
    term_pattern,
    term_tokens,
    visible_text,
)
from .quality import LIMITATIONS_NOTE, build_quality_report, quality_report_to_json
from .taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    SkillDefinition,
    Taxonomy,
    load_taxonomy,
    taxonomy_from_dict,
)
from .visualizations import (
    build_visualizations,
    svg_category_coverage,
    svg_cooccurrence_matrix,
    svg_skill_frequency,
    zero_match_markdown,
)

__all__ = [
    "ANALYSIS_KIND",
    "ANALYSIS_VERSION",
    "ANNOTATION_DATE",
    "AnalysisError",
    "DATASET_KIND",
    "DATASET_TYPE",
    "DATASET_VERSION",
    "DatasetError",
    "DatasetIntegrityError",
    "DescriptiveError",
    "EVALUATION_ARTIFACT_DEFAULT_PATH",
    "EVALUATION_KIND",
    "EVALUATION_STATUS",
    "EVALUATION_VERSION",
    "EVIDENCE_FIELDS",
    "EXCERPT_CONTEXT_CHARS",
    "EvaluationError",
    "JobSkillResult",
    "LABEL_VALUES",
    "LIMITATIONS_NOTE",
    "MATCHER_VERSION",
    "REPORT_ARTIFACT_DEFAULT_PATH",
    "SAMPLE_LIMIT",
    "SAMPLE_OFFSET",
    "SAMPLE_PAGE",
    "SAMPLE_RECORDS",
    "SEARCHED_FIELDS",
    "SNAPSHOT_ID",
    "SkillDefinition",
    "SkillMatch",
    "TAXONOMY_ARTIFACT_DEFAULT_PATH",
    "TAXONOMY_VERSION",
    "Taxonomy",
    "TaxonomyError",
    "build_descriptive_analysis",
    "build_development_dataset",
    "build_contingency",
    "build_quality_report",
    "build_report",
    "build_visualizations",
    "category_coverage",
    "compute_metrics",
    "cooccurrence_matrix",
    "cooccurrence_pairs",
    "evaluation_from_dict",
    "field_text",
    "load_evaluation",
    "load_taxonomy",
    "match_job",
    "predictions_by_record",
    "quality_freshness_summary",
    "quality_report_to_json",
    "resolve_quote_span",
    "resolve_snapshot_id",
    "serialize_analysis",
    "serialize_dataset",
    "serialize_evaluation",
    "serialize_report",
    "skill_frequency",
    "svg_category_coverage",
    "svg_cooccurrence_matrix",
    "svg_skill_frequency",
    "taxonomy_from_dict",
    "term_pattern",
    "term_tokens",
    "validate_development_sample",
    "validate_evaluation",
    "visible_text",
    "zero_match_markdown",
    "zero_match_skills",
]
