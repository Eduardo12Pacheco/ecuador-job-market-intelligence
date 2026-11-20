"""Análisis descriptivo determinista para la muestra de desarrollo.

Este módulo calcula las métricas del hito de visualización descriptiva SOLO desde el
conjunto de datos analítico existente (``data/analytics/development-sample-0.1.0.json``).
El artefacto de taxonomía versionado (``data/taxonomy/technical-skills-0.1.0.json``)
se usa únicamente como búsqueda de esquema local para nombres/categorías canónicos;
no es una fuente observacional. No se consultan páginas crudas, manifiestos, respuestas
de API ni red, y no se lee ningún reloj de pared.

El análisis es de cierre. ``validate_development_sample`` rechaza cualquier
conjunto de datos que no sea exactamente la muestra de desarrollo documentada:

- ``dataset_kind`` debe ser ``development_sample``;
- la muestra debe tener exactamente la forma acotada declarada: 20 registros, una página
  (``page=1``, ``limit=20``, ``offset=0``), con ``complete: false``;
- la identidad del snapshot debe ser ``cap_0370798f7af4b0e3``;
- la versión del artefacto de taxonomía debe coincidir con el ``taxonomy_version`` del conjunto de datos.

Definiciones (todos los conteos son a nivel de registro, nunca conteos de apariciones textuales):

- **Frecuencia de habilidades**: el número de registros distintos cuyo conjunto de
  habilidades único por registro contiene la habilidad. Una habilidad cuenta como
  máximo una vez por registro aunque sus términos aparezcan muchas veces en el texto.
- **Cobertura por categoría**: el número de registros distintos con al menos una
  habilidad coincidente en la categoría; un registro cuenta como máximo una vez por categoría.
- **Habilidades sin coincidencias**: habilidades de la taxonomía con cero registros
  coincidentes. Un cero NO es evidencia de que los empleos carezcan de la habilidad, y
  es distinto de los registros ``no_evidence`` (registros donde la taxonomía no encontró
  ninguna palabra clave).
- **Pares de coocurrencia**: pares sin orden de habilidades distintas construidos desde
  los conjuntos de habilidades únicos por registro; cada par es canónico ``(skill_a, skill_b)``
  con ``skill_a < skill_b``, nunca reflexivo, nunca duplicado en orden inverso y contado
  una vez por registro.
- **Matriz de coocurrencia**: una matriz simétrica sobre todos los ids de habilidades de
  la taxonomía ordenados; la celda ``[i][j]`` es el número de registros distintos que
  contienen ambas habilidades. La diagonal es cero por definición (sin auto-pares).

El artefacto además copia el informe de calidad embebido del conjunto de datos sin
cambiar su significado y añade salvaguardas explícitas: la salida es solo evidencia
descriptiva de palabras clave y NO es correlación, causalidad, cobertura de mercado ni
representatividad.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .dataset import DATASET_KIND
from .errors import DescriptiveError
from .taxonomy import Taxonomy

#: Versión del diseño del análisis descriptivo (subir cuando cambie el diseño).
ANALYSIS_VERSION = "0.1.0"

#: El discriminador de tipo del artefacto.
ANALYSIS_KIND = "descriptive_visualization"

#: El contrato documentado de la muestra de desarrollo (ver el artefacto del conjunto de datos).
SAMPLE_RECORDS = 20
SAMPLE_PAGE = 1
SAMPLE_LIMIT = 20
SAMPLE_OFFSET = 0

#: La identidad de snapshot documentada de la muestra de desarrollo (del
#: manifiesto de captura persistido; nunca inventada).
SNAPSHOT_ID = "cap_0370798f7af4b0e3"

GUARDRAILS = (
    "descriptive keyword evidence only: every metric is derived from the deterministic "
    "keyword baseline applied to the development sample; no embeddings, LLMs, semantic "
    "search, or fuzzy inference were used",
    "not correlation: cooccurrence counts how often two skills appear in the same "
    "records; it does not measure any relationship, association, or dependency between "
    "skills",
    "not causality: no metric here claims that one skill causes, predicts, or is required by another",
    "not market coverage: the analysis covers exactly 20 records from one page "
    "(limit=20, offset=0) of one source (Himalayas), marked complete: false; it is not "
    "a market snapshot and no whole-market claim is made",
    "not representative: this single-page sample of one job board is not representative "
    "of the Ecuadorian labor market or of any broader job market",
    "no_evidence vs zero matches: no_evidence records are records where the taxonomy "
    "found no keyword at all; a taxonomy skill with zero matches in this sample is not "
    "evidence that jobs lack that skill",
)

_DEFINITIONS = {
    "skill_frequency": (
        "number of distinct records whose unique per-record skill set contains the "
        "skill; a skill counts at most once per record even when its terms occur many "
        "times in the record's text"
    ),
    "category_coverage": (
        "number of distinct records that have at least one matched skill in the "
        "category; a record is counted at most once per category even when several of "
        "its matched skills belong to the same category"
    ),
    "cooccurrence_pairs": (
        "unordered pairs of distinct skills built from unique per-record skill sets; "
        "each pair is canonical (skill_a < skill_b), never reflexive, never duplicated "
        "in reverse order, and counted once per record"
    ),
    "cooccurrence_matrix": (
        "symmetric matrix over all taxonomy skill ids (sorted); cell [i][j] is the "
        "number of distinct records containing both skills; the diagonal is zero by "
        "definition (no self-pairs)"
    ),
    "zero_match_skills": (
        "taxonomy skills with zero matched records in the sample; a zero match is NOT "
        "evidence that jobs lack the skill, and it is distinct from no_evidence "
        "records (records where the taxonomy found no keyword at all)"
    ),
}


def _skill_sets(records: Sequence[Mapping[str, Any]]) -> list[frozenset[str]]:
    """Conjuntos de habilidades únicos por registro (defensivo: los ids repetidos colapsan)."""
    sets: list[frozenset[str]] = []
    for record in records:
        evidence = record.get("skill_evidence") or {}
        skills = evidence.get("skills") or []
        sets.append(frozenset(s for s in skills if isinstance(s, str) and s))
    return sets


def validate_development_sample(dataset: Mapping[str, Any], taxonomy: Taxonomy) -> None:
    """Falla de forma cerrada cuando el conjunto de datos no es la muestra de desarrollo documentada.

    Eleva :class:`DescriptiveError` ante cualquier desviación: ``dataset_kind``
    equivocado, una muestra que no tenga exactamente la forma acotada declarada de
    20 registros/una página (``page=1``, ``limit=20``, ``offset=0``, 20 registros),
    ``complete: true``, una identidad de snapshot distinta o una versión del
    artefacto de taxonomía que no coincida con el ``taxonomy_version`` del conjunto
    de datos.
    """
    if not isinstance(dataset, dict):
        raise DescriptiveError("el conjunto de datos debe ser un objeto JSON")
    if dataset.get("dataset_kind") != DATASET_KIND:
        raise DescriptiveError(
            f"dataset_kind debe ser 'development_sample' para el análisis descriptivo; "
            f"se obtuvo {dataset.get('dataset_kind')!r}"
        )
    if dataset.get("taxonomy_version") != taxonomy.version:
        raise DescriptiveError(
            f"la versión de la taxonomía no coincide: el conjunto de datos declara "
            f"{dataset.get('taxonomy_version')!r} pero el artefacto de taxonomía es "
            f"{taxonomy.version!r}; se rechaza analizar con una taxonomía distinta"
        )
    sample = dataset.get("sample")
    if not isinstance(sample, dict):
        raise DescriptiveError("el conjunto de datos no tiene un objeto de metadatos 'sample'")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise DescriptiveError("el conjunto de datos no tiene una lista 'records'")
    for label, actual, expected in (
        ("records", sample.get("records"), SAMPLE_RECORDS),
        ("page", sample.get("page"), SAMPLE_PAGE),
        ("offset", sample.get("offset"), SAMPLE_OFFSET),
        ("limit", sample.get("limit"), SAMPLE_LIMIT),
    ):
        if actual != expected:
            raise DescriptiveError(
                f"sample.{label} debe ser {expected} para la muestra de desarrollo documentada; se obtuvo {actual!r}"
            )
    if len(records) != SAMPLE_RECORDS:
        raise DescriptiveError(
            f"el conjunto de datos lleva {len(records)} registros; la muestra de desarrollo "
            f"documentada tiene exactamente {SAMPLE_RECORDS}"
        )
    if sample.get("complete") is not False:
        raise DescriptiveError(
            "sample.complete debe ser false para la muestra de desarrollo; se rechaza analizar una muestra 'complete'"
        )
    identity = dataset.get("capture_identity")
    if not isinstance(identity, dict) or identity.get("snapshot_id") != SNAPSHOT_ID:
        raise DescriptiveError(
            f"la identidad del snapshot debe ser {SNAPSHOT_ID} (la muestra de desarrollo "
            f"documentada); se rechaza analizar una captura distinta"
        )


def skill_frequency(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Recuentos por registro distinto de cada habilidad (una habilidad cuenta como máximo una vez por registro)."""
    counts: dict[str, int] = {}
    for skills in _skill_sets(records):
        for skill_id in skills:
            counts[skill_id] = counts.get(skill_id, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def category_coverage(records: Sequence[Mapping[str, Any]], taxonomy: Taxonomy) -> dict[str, Any]:
    """Cobertura por registro distinto por categoría, con la definición incluida."""
    category_by_skill = {skill.skill_id: skill.category for skill in taxonomy.skills}
    records_per_category: dict[str, set[int]] = {}
    matched_per_category: dict[str, set[str]] = {}
    for index, skills in enumerate(_skill_sets(records)):
        present = {category_by_skill[s] for s in skills if s in category_by_skill}
        for category in present:
            records_per_category.setdefault(category, set()).add(index)
        for skill_id in skills:
            if skill_id in category_by_skill:
                matched_per_category.setdefault(category_by_skill[skill_id], set()).add(skill_id)
    total = {
        category: sum(1 for skill in taxonomy.skills if skill.category == category) for category in taxonomy.categories
    }
    categories = [
        {
            "category": category,
            "records": len(records_per_category.get(category, ())),
            "matched_skills": sorted(matched_per_category.get(category, ())),
            "matched_skill_count": len(matched_per_category.get(category, ())),
            "total_taxonomy_skills": total[category],
        }
        for category in taxonomy.categories
    ]
    categories.sort(key=lambda entry: (-entry["records"], entry["category"]))
    return {
        "definition": _DEFINITIONS["category_coverage"],
        "categories": categories,
    }


def zero_match_skills(records: Sequence[Mapping[str, Any]], taxonomy: Taxonomy) -> dict[str, Any]:
    """Habilidades de la taxonomía con cero registros coincidentes, con la distinción no_evidence."""
    matched = set(skill_frequency(records))
    skills = [
        {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "category": skill.category,
            "matched_records": 0,
        }
        for skill in taxonomy.skills
        if skill.skill_id not in matched
    ]
    skills.sort(key=lambda entry: entry["skill_id"])
    return {
        "definition": _DEFINITIONS["zero_match_skills"],
        "count": len(skills),
        "skills": skills,
    }


def cooccurrence_pairs(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pares de coocurrencia sin orden, canónicos y contados una vez por registro."""
    counts: dict[tuple[str, str], int] = {}
    for skills in _skill_sets(records):
        ordered = sorted(skills)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pair = (ordered[i], ordered[j])
                counts[pair] = counts.get(pair, 0) + 1
    pairs = [{"skill_a": skill_a, "skill_b": skill_b, "records": count} for (skill_a, skill_b), count in counts.items()]
    pairs.sort(key=lambda pair: (-pair["records"], pair["skill_a"], pair["skill_b"]))
    return {
        "definition": _DEFINITIONS["cooccurrence_pairs"],
        "pair_count": len(pairs),
        "pairs": pairs,
    }


def cooccurrence_matrix(records: Sequence[Mapping[str, Any]], taxonomy: Taxonomy) -> dict[str, Any]:
    """Matriz de coocurrencia simétrica sobre los ids de habilidad de la taxonomía ordenados (diagonal cero)."""
    skill_ids = sorted(skill.skill_id for skill in taxonomy.skills)
    index = {skill_id: i for i, skill_id in enumerate(skill_ids)}
    size = len(skill_ids)
    matrix = [[0] * size for _ in range(size)]
    for skills in _skill_sets(records):
        for skill_a in skills:
            if skill_a not in index:
                continue
            for skill_b in skills:
                if skill_b not in index or skill_a >= skill_b:
                    continue
                matrix[index[skill_a]][index[skill_b]] += 1
                matrix[index[skill_b]][index[skill_a]] += 1
    return {
        "skill_ids": skill_ids,
        "matrix": matrix,
        "diagonal": (
            "zero by definition — a skill never cooccurs with itself (no self-pairs); "
            "the matrix is symmetric and each cell counts distinct records"
        ),
    }


def quality_freshness_summary(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Resume el informe de calidad embebido sin cambiar su significado."""
    report = dataset.get("quality_report") or {}
    coverage = report.get("skill_coverage") or {}
    return {
        "record_count": report.get("record_count"),
        "checked_fields": list(report.get("checked_fields", [])),
        "missing_field_counts": dict(report.get("missing_field_counts", {})),
        "duplicate_source_id_records": (report.get("duplicate_counts") or {}).get("duplicate_source_id_records"),
        "observation_status_counts": dict(report.get("observation_status_counts", {})),
        "records_with_evidence": coverage.get("records_with_evidence"),
        "records_without_evidence": coverage.get("records_without_evidence"),
        "no_evidence_record_ids": list(coverage.get("records_no_evidence", [])),
        "age_at_capture_seconds": (report.get("freshness") or {}).get("age_at_capture_seconds"),
        "freshness_formula": (report.get("freshness") or {}).get("formula"),
        "limitations_note": report.get("limitations_note"),
    }


def build_descriptive_analysis(dataset: Mapping[str, Any], taxonomy: Taxonomy) -> dict[str, Any]:
    """Construye el artefacto de análisis descriptivo determinista para la muestra.

    Valida el contrato documentado de la muestra de desarrollo, calcula las métricas
    a nivel de registro, copia el informe de calidad embebido y adjunta metadatos,
    definiciones, avisos, limitaciones y salvaguardas. Eleva :class:`DescriptiveError`
    cuando el conjunto de datos no es la muestra documentada o cuando la frecuencia de
    habilidades calculada contradice el informe de calidad embebido.
    """
    validate_development_sample(dataset, taxonomy)
    records = dataset["records"]
    frequencies = skill_frequency(records)

    report = dataset.get("quality_report") or {}
    embedded_counts = (report.get("skill_coverage") or {}).get("skill_counts") or {}
    # Alinear ambos lados sobre el conjunto completo de habilidades de la taxonomía (conteos cero incluidos).
    expected = {skill.skill_id: embedded_counts.get(skill.skill_id, 0) for skill in taxonomy.skills}
    actual = {skill.skill_id: frequencies.get(skill.skill_id, 0) for skill in taxonomy.skills}
    if actual != expected:
        raise DescriptiveError(
            "la frecuencia de habilidades calculada no coincide con el informe de calidad embebido; "
            "se rechaza producir un artefacto de análisis inconsistente"
        )

    identity = dataset["capture_identity"]
    sample = dataset["sample"]
    return {
        "analysis_version": ANALYSIS_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "source": identity.get("source"),
        "endpoint": identity.get("endpoint"),
        "attribution_url": identity.get("attribution_url"),
        "dataset_kind": dataset["dataset_kind"],
        "dataset_version": dataset.get("dataset_version"),
        "taxonomy_version": dataset["taxonomy_version"],
        "matcher_version": dataset.get("matcher_version"),
        "snapshot_id": identity.get("snapshot_id"),
        "snapshot_id_origin": identity.get("snapshot_id_origin"),
        "capture_id": identity.get("capture_id"),
        "raw_sha256": identity.get("raw_sha256"),
        "captured_at": identity.get("captured_at"),
        "sample": {
            "page": sample["page"],
            "offset": sample["offset"],
            "limit": sample["limit"],
            "records": sample["records"],
            "total_count": sample.get("total_count"),
            "complete": sample["complete"],
            "warning": (
                f"development_sample: exactly {SAMPLE_RECORDS} records from one bounded "
                f"page (limit={sample['limit']}, offset={sample['offset']}), snapshot "
                f"{SNAPSHOT_ID}, taxonomy {taxonomy.version}, complete: false — this is "
                "not a full feed and not market coverage"
            ),
        },
        "definitions": dict(_DEFINITIONS),
        "skill_frequency": frequencies,
        "category_coverage": category_coverage(records, taxonomy),
        "zero_match_skills": zero_match_skills(records, taxonomy),
        "cooccurrence_pairs": cooccurrence_pairs(records),
        "cooccurrence_matrix": cooccurrence_matrix(records, taxonomy),
        "quality_report": report,
        "quality_freshness_summary": quality_freshness_summary(dataset),
        "guardrails": list(GUARDRAILS),
        "warnings": [
            "development_sample: exactly 20 records, one page (limit=20, offset=0), "
            "complete: false; the analysis is bounded to the single authorized capture",
            "descriptive keyword evidence only: the metrics are derived from the "
            "deterministic keyword baseline (technical-skills-0.1.0); no semantic, "
            "LLM, or embedding analysis was used",
        ],
        "limitations": list(sample.get("limitations", [])),
        "streamlit_status": (
            "pending — the interactive Streamlit demo is not implemented; these "
            "offline artifacts are the baseline visualizations"
        ),
    }


def serialize_analysis(analysis: Mapping[str, Any]) -> bytes:
    """Serialización JSON determinista en UTF-8 (claves ordenadas, sangría de 2 espacios, salto de línea)."""
    return (json.dumps(analysis, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
