"""Informe de calidad determinista para el conjunto de datos de desarrollo.

El informe se deriva exclusivamente de las entradas del conjunto de datos de
desarrollo (la proyección canónica, los resultados de coincidencia y el manifiesto
persistido). No se consulta ningún reloj de pared, de modo que el informe es
reproducible byte por byte.

Definiciones explícitas:

- **Campos verificados**: los mismos cuatro campos que busca el matcher
  (``title_raw``, ``excerpt_raw``, ``categories_raw``, ``description_html_raw``).
  Un campo cuenta como faltante cuando es ``None``, una cadena vacía o una lista
  vacía — la misma definición que usa el matcher para omitir campos, de modo que
  los campos omitidos y los conteos de campos faltantes siempre coinciden.
- **Duplicados**: dos registros con el mismo ``source_id`` no vacío dentro de esta
  muestra. Los registros con ``source_id`` vacío (entradas inválidas) se excluyen
  de la detección de duplicados y se cuentan bajo ``observation_status_counts``.
- **Cobertura de habilidades**: una habilidad cuenta una vez por registro
  (deduplicada). Toda habilidad de la taxonomía aparece en ``skill_counts``,
  incluidas las entradas con cero.
- **Frescura**: ``age_at_capture_seconds = captured_at -
  api_updated_at_utc``, ambas marcas de tiempo con zona horaria leídas del
  manifiesto persistido; el cálculo nunca consulta la hora actual y es seguro por
  construcción frente a zonas horarias (ambos lados se convierten a UTC primero).
- **Limitaciones**: el informe siempre declara que solo se incluyen 20 registros de
  una página y que esto no es cobertura de mercado.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..ingestion.models import CanonicalJob
from .matcher import SEARCHED_FIELDS, JobSkillResult, field_text
from .taxonomy import Taxonomy

LIMITATIONS_NOTE = (
    "development sample: only 20 records from one page (limit=20, offset=0) of one source are "
    "included; the capture is marked complete: false, no full feed has been captured, and this "
    "is not market coverage. Matches are keyword evidence only; no_evidence is not evidence of "
    "absence, and no semantic, LLM, or embedding analysis is performed."
)

FRESHNESS_FORMULA = (
    "age_at_capture_seconds = captured_at - api_updated_at_utc; both values are UTC-aware "
    "timestamps read from the persisted capture manifest (no wall clock is consulted)"
)


def _manifest_captured_at(manifest: Mapping[str, Any]) -> datetime | None:
    raw = manifest.get("captured_at")
    if raw is None:
        return None
    try:
        value = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value


def build_quality_report(
    jobs: Sequence[CanonicalJob],
    results: Sequence[JobSkillResult],
    *,
    manifest: Mapping[str, Any],
    taxonomy: Taxonomy,
) -> dict:
    """Construye el dict del informe de calidad determinista de un conjunto de datos de desarrollo."""
    job_list = list(jobs)
    result_list = list(results)
    if len(job_list) != len(result_list):
        raise ValueError("jobs y results deben tener la misma longitud")

    # Conteos de campos faltantes sobre el conjunto de campos verificado (buscado) explícito.
    missing_counts: dict[str, int] = {}
    for field in SEARCHED_FIELDS:
        missing_counts[field] = sum(1 for job in job_list if field_text(job, field) is None)

    # Detección de duplicados sobre source_ids no vacíos (los registros inválidos se excluyen).
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    duplicate_record_count = 0
    for job in job_list:
        if not job.source_id:
            continue
        if job.source_id in seen:
            duplicate_record_count += 1
            duplicate_ids.add(job.source_id)
        else:
            seen.add(job.source_id)

    # Cobertura de habilidades: un conteo por registro, con todas las habilidades de la taxonomía.
    per_skill: dict[str, int] = {skill.skill_id: 0 for skill in taxonomy.skills}
    records_with_evidence = 0
    no_evidence_ids: list[str] = []
    for job, result in zip(job_list, result_list):
        if result.evidence_status == "matched":
            records_with_evidence += 1
            for skill_id in result.skills:
                if skill_id in per_skill:
                    per_skill[skill_id] += 1
        else:
            no_evidence_ids.append(job.canonical_id)
    skill_counts = dict(sorted(per_skill.items(), key=lambda item: (-item[1], item[0])))
    no_evidence_ids.sort()

    # Frescura: explícita, segura frente a zonas horarias y solo desde el manifiesto.
    captured_at = _manifest_captured_at(manifest)
    updated_raw = manifest.get("updated_at_utc")
    updated_at_utc: datetime | None = None
    if updated_raw is not None:
        try:
            parsed = datetime.fromisoformat(str(updated_raw))
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None and parsed.tzinfo is not None:
            updated_at_utc = parsed.astimezone(timezone.utc)
    if captured_at is not None and updated_at_utc is not None:
        age = (captured_at - updated_at_utc).total_seconds()
    else:
        age = None

    return {
        "record_count": len(job_list),
        "checked_fields": list(SEARCHED_FIELDS),
        "missing_field_counts": missing_counts,
        "duplicate_counts": {
            "duplicate_source_id_records": duplicate_record_count,
            "duplicate_source_ids": sorted(duplicate_ids),
        },
        "observation_status_counts": {
            status: count
            for status, count in sorted(
                Counter(job.observation_status.value for job in job_list).items()
            )
        },
        "skill_coverage": {
            "taxonomy_version": taxonomy.version,
            "records_with_evidence": records_with_evidence,
            "records_without_evidence": len(job_list) - records_with_evidence,
            "records_no_evidence": no_evidence_ids,
            "skill_counts": skill_counts,
        },
        "freshness": {
            "source_updated_at_utc": manifest.get("updated_at_utc"),
            "captured_at": manifest.get("captured_at"),
            "age_at_capture_seconds": age,
            "formula": FRESHNESS_FORMULA,
        },
        "limitations_note": LIMITATIONS_NOTE,
    }


def quality_report_to_json(report: dict) -> bytes:
    """Serialización JSON determinista del informe de calidad (uso de prueba/utilidad)."""
    return (json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
