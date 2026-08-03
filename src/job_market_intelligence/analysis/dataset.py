"""Conjunto de datos analítico canónico de desarrollo (determinista, totalmente offline).

``build_development_dataset`` proyecta una proyección canónica existente (una
secuencia de :class:`~job_market_intelligence.ingestion.models.CanonicalJob`
proporcionada por quien llama) más los metadatos de captura persistidos en un
conjunto de datos de desarrollo versionado:

- Cada campo canónico se conserva valor-por-valor, incluidos todos los campos
  ``*_raw`` y ``snapshot_id``. Nada crudo se modifica.
- Las únicas adiciones son evidencia de habilidades derivada y transparente de la
  línea base determinista de palabras clave (ver :mod:`matcher`); ninguna habilidad
  se infiere más allá de las reglas de palabras clave de la taxonomía.
- Un registro sin coincidencias es explícitamente ``no_evidence`` con ``skills: []``;
  nunca es un hecho vacío que implique que no existe ninguna habilidad.
- El conjunto de datos está marcado ``development_sample`` y lleva la fuente, la
  identidad de manifiesto/captura, página/offset/limit, la versión de taxonomía y
  las limitaciones de muestra.
- ``sample.complete`` siempre es ``false`` — un invariante duro de la ruta de la
  muestra de desarrollo. Un manifiesto que declare ``complete: true`` se rechaza con
  :class:`DatasetError` (cierre ante fallos) en lugar de heredarse, de modo que quien
  llama nunca puede producir una muestra de desarrollo «completa».
- Las entradas de evidencia registran el ``matched_term`` (keyword o alias) y su
  ``term_type``; los términos son únicos en toda la taxonomía por construcción del
  cargador.
- La salida es reproducible: ordenamiento estable de registros y evidencia,
  serialización JSON determinista (``sort_keys`` + sangría fija) y sin campos de
  reloj de pared. Las únicas marcas de tiempo son los metadatos de captura/fuente ya
  persistidos en el manifiesto.
- La identidad del snapshot proviene del ``capture_id`` del manifiesto (la identidad
  de captura estable documentada derivada de la captura cruda persistida) o de un
  argumento explícito ``snapshot_id``. Un manifiesto sin ``capture_id`` y sin argumento
  explícito falla de forma cerrada: nunca se inventa un identificador aleatorio.

El artefacto materializado embebe el informe de :mod:`quality` para que el conjunto
de datos y el informe describan siempre los mismos bytes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..ingestion.models import CanonicalJob
from .errors import DatasetError, DatasetIntegrityError
from .matcher import MATCHER_VERSION, JobSkillResult, match_job
from .quality import build_quality_report
from .taxonomy import Taxonomy

#: Versión del diseño del conjunto de datos de desarrollo (subir cuando cambie el diseño).
DATASET_VERSION = "0.1.0"

#: El conjunto de datos es explícitamente una muestra de desarrollo, nunca un snapshot de mercado.
DATASET_KIND = "development_sample"

_REQUIRED_MANIFEST_KEYS = (
    "source",
    "endpoint",
    "request_params",
    "limit",
    "offset",
    "captured_at",
    "updated_at_raw",
    "updated_at_utc",
    "timestamp_unit",
    "total_count",
    "returned_jobs",
    "raw_file_path",
    "raw_sha256",
    "adapter_version",
    "attribution_url",
    "complete",
    "warnings",
    "errors",
)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def resolve_snapshot_id(manifest: Mapping[str, Any], snapshot_id: str | None = None) -> tuple[str, str]:
    """Resuelve la identidad del snapshot del conjunto de datos y su origen.

    Determinista y de cierre: el ``capture_id`` del manifiesto es la identidad de
    captura estable documentada derivada de la captura persistida; un argumento
    explícito prevalece. Nunca se inventa un id de snapshot aleatorio.
    """
    if snapshot_id is not None:
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise DatasetError("snapshot_id debe ser una cadena no vacía")
        return snapshot_id, "explicit"
    capture_id = manifest.get("capture_id")
    if not isinstance(capture_id, str) or not capture_id:
        raise DatasetError(
            "el manifiesto no tiene capture_id y no se dio ningún snapshot_id explícito; "
            "nunca se inventa un id de snapshot aleatorio — pasar snapshot_id explícitamente"
        )
    return capture_id, "manifest_capture_id"


def _manifest_captured_at(manifest: Mapping[str, Any]) -> datetime:
    raw = manifest.get("captured_at")
    try:
        captured_at = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError) as exc:
        raise DatasetIntegrityError(f"el 'captured_at' del manifiesto no es ISO 8601: {raw!r}") from exc
    if captured_at.tzinfo is None:
        raise DatasetIntegrityError(
            f"el 'captured_at' del manifiesto es timezone-naive (ingenuo en zona horaria): {raw!r}; se rechaza adivinar una zona"
        )
    return captured_at.astimezone(timezone.utc)


def _check_capture_clock(jobs: Sequence[CanonicalJob], captured_at: datetime) -> None:
    for job in jobs:
        if job.first_seen_at.astimezone(timezone.utc) != captured_at:
            raise DatasetIntegrityError(
                "el first_seen_at del empleo canónico no coincide con el captured_at del manifiesto; "
                "la proyección debe parsearse con el momento de captura persistido"
            )


def _record_dict(job: CanonicalJob, result: JobSkillResult) -> dict:
    record = {
        "canonical_id": job.canonical_id,
        "source": job.source,
        "source_id": job.source_id,
        "source_url": job.source_url,
        "application_url": job.application_url,
        "snapshot_id": job.snapshot_id,
        "title_raw": job.title_raw,
        "company_raw": job.company_raw,
        "company_slug_raw": job.company_slug_raw,
        "excerpt_raw": job.excerpt_raw,
        "description_html_raw": job.description_html_raw,
        "location_restrictions_raw": list(job.location_restrictions_raw),
        "location_scope": job.location_scope.value,
        "timezone_restrictions_raw": list(job.timezone_restrictions_raw),
        "employment_type_raw": job.employment_type_raw,
        "seniority_raw": list(job.seniority_raw),
        "categories_raw": list(job.categories_raw),
        "salary_min_raw": job.salary_min_raw,
        "salary_max_raw": job.salary_max_raw,
        "salary_period_raw": job.salary_period_raw,
        "currency_raw": job.currency_raw,
        "published_at_raw": job.published_at_raw,
        "published_at_utc": _utc_iso(job.published_at_utc) if job.published_at_utc is not None else None,
        "expires_at_raw": job.expires_at_raw,
        "expires_at_utc": _utc_iso(job.expires_at_utc) if job.expires_at_utc is not None else None,
        "first_seen_at": _utc_iso(job.first_seen_at),
        "last_seen_at": _utc_iso(job.last_seen_at),
        "observation_status": job.observation_status.value,
        "quality_flags": list(job.quality_flags),
        "skill_evidence": {
            "evidence_status": result.evidence_status,
            "taxonomy_version": result.taxonomy_version,
            "matcher_version": MATCHER_VERSION,
            "skills": list(result.skills),
            "evidence": [
                {
                    "skill_id": entry.skill_id,
                    "field": entry.field,
                    "matched_term": entry.matched_term,
                    "term_type": entry.term_type,
                    "excerpt": entry.excerpt,
                    "occurrence_count": entry.occurrence_count,
                }
                for entry in result.evidence
            ],
            "searched_fields": list(result.searched_fields),
            "skipped_fields": list(result.skipped_fields),
        },
    }
    return record


def build_development_dataset(
    jobs: Sequence[CanonicalJob],
    *,
    manifest: Mapping[str, Any],
    taxonomy: Taxonomy,
    snapshot_id: str | None = None,
    manifest_path: str | None = None,
) -> dict:
    """Construye el conjunto de datos de desarrollo versionado desde una proyección canónica.

    ``jobs`` debe ser la proyección canónica de la captura persistida parseada con
    el ``captured_at`` del manifiesto; un desajuste de reloj falla de forma cerrada.
    ``manifest`` debe llevar los metadatos de captura obligatorios (ver
    :data:`_REQUIRED_MANIFEST_KEYS`). Devuelve un dict serializable a JSON.
    """
    missing = [key for key in _REQUIRED_MANIFEST_KEYS if key not in manifest]
    if missing:
        raise DatasetError(f"al manifiesto le faltan claves obligatorias: {', '.join(sorted(missing))}")

    captured_at = _manifest_captured_at(manifest)
    _check_capture_clock(jobs, captured_at)
    resolved_id, origin = resolve_snapshot_id(manifest, snapshot_id)

    if bool(manifest["complete"]):
        raise DatasetError(
            "el manifiesto declara complete: true, pero la ruta de la muestra de desarrollo solo "
            "puede producir muestras complete: false; se rechaza construir una muestra completa"
        )

    results = [match_job(job, taxonomy) for job in jobs]
    records = [_record_dict(job, result) for job, result in zip(jobs, results)]

    limit = manifest["limit"]
    offset = manifest["offset"]
    page = offset // limit + 1 if isinstance(limit, int) and limit else 1

    dataset = {
        "dataset_version": DATASET_VERSION,
        "dataset_kind": DATASET_KIND,
        "taxonomy_version": taxonomy.version,
        "matcher_version": MATCHER_VERSION,
        "capture_identity": {
            "source": manifest["source"],
            "endpoint": manifest["endpoint"],
            "snapshot_id": resolved_id,
            "snapshot_id_origin": origin,
            "capture_id": manifest.get("capture_id"),
            "adapter_version": manifest["adapter_version"],
            "attribution_url": manifest["attribution_url"],
            "raw_file_path": manifest["raw_file_path"],
            "raw_sha256": manifest["raw_sha256"],
            "manifest_path": manifest_path,
            "captured_at": _utc_iso(captured_at),
            "api_updated_at_raw": manifest["updated_at_raw"],
            "api_updated_at_utc": manifest["updated_at_utc"],
            "timestamp_unit": manifest["timestamp_unit"],
            "manifest_errors": list(manifest["errors"]),
        },
        "sample": {
            "page": page,
            "offset": offset,
            "limit": limit,
            "records": len(records),
            "total_count": manifest["total_count"],
            "complete": False,  # invariante de la ruta de la muestra de desarrollo (ver la salvaguarda anterior)
            "warnings": list(manifest["warnings"]),
            "limitations": [
                "development_sample: only the records of one persisted page are included "
                f"(limit={limit}, offset={offset}); this is a bounded capture, not a full feed",
                "complete: false — the development-sample path always marks the sample "
                "incomplete: this is a bounded single-page capture, not a complete-feed "
                "snapshot, and this is not market coverage",
                "matches are keyword evidence only; no_evidence means the taxonomy found "
                "no keyword in the searched fields, not that the skill is absent",
                "raw fields and the snapshot/capture identity are retained unchanged; "
                "derived skill evidence is purely additive",
            ],
        },
        "records": records,
        "quality_report": build_quality_report(
            list(jobs), results, manifest=manifest, taxonomy=taxonomy
        ),
    }
    return dataset


def serialize_dataset(dataset: dict) -> bytes:
    """Serialización JSON determinista en UTF-8 (claves ordenadas, sangría de 2 espacios, salto de línea final)."""
    return (
        json.dumps(dataset, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
