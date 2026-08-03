"""Capa de demostración interactiva: carga tolerante y testeable de artefactos para la app.

El paquete demo existe para que ``app/evidence_desk.py`` se mantenga delgado y para
que la lógica de carga/normalización sea testeable por unidades sin Streamlit. Lee
los cinco artefactos versionados bajo ``data/`` y los normaliza para la
visualización con respaldos por campo: un campo opcional faltante degrada a un
marcador visible (``Untitled role``, ``Unknown company``, ``Not disclosed``,
extracto vacío), mientras que un archivo de artefacto faltante o ilegible lanza
:class:`DemoDataError` para que la app pueda mostrar un mensaje de recuperación en
lugar de fallar.

La capa demo es solo de visualización. Nunca modifica artefactos y nunca reemplaza
los cargadores de la tubería con cierre ante fallo (``analysis.taxonomy``,
``analysis.evaluation``, ``analysis.second_pass``) que validan la procedencia en
tiempo de materialización.
"""

from .artifacts import (
    CATEGORY_LABELS,
    DATASET_PATH,
    DESCRIPTIVE_PATH,
    DemoBundle,
    DemoDataError,
    DemoDataset,
    EvidenceEntry,
    JobRecord,
    REPORT_PATH,
    REVIEW_PATH,
    ReviewEvidence,
    ReviewLabel,
    ReviewReport,
    ReviewSet,
    SkillInfo,
    TAXONOMY_PATH,
    TaxonomyInfo,
    category_coverage,
    format_metric,
    load_demo_bundle,
    load_dataset,
    load_descriptive,
    load_report,
    load_review,
    load_taxonomy_info,
    prettify_slug,
    skill_frequency,
    verify_quote,
    zero_match_skills,
)

__all__ = [
    "CATEGORY_LABELS",
    "DATASET_PATH",
    "DESCRIPTIVE_PATH",
    "DemoBundle",
    "DemoDataError",
    "DemoDataset",
    "EvidenceEntry",
    "JobRecord",
    "REPORT_PATH",
    "REVIEW_PATH",
    "ReviewEvidence",
    "ReviewLabel",
    "ReviewReport",
    "ReviewSet",
    "SkillInfo",
    "TAXONOMY_PATH",
    "TaxonomyInfo",
    "category_coverage",
    "format_metric",
    "load_demo_bundle",
    "load_dataset",
    "load_descriptive",
    "load_report",
    "load_review",
    "load_taxonomy_info",
    "prettify_slug",
    "skill_frequency",
    "verify_quote",
    "zero_match_skills",
]
