"""Objetos de valor tipados del contrato de ingesta de Himalayas.

Refleja ``docs/ingestion/himalayas-adapter-contract.md``: un
:class:`Snapshot` describe una ejecución completa de recolección y es el
único lugar donde vive ``updatedAt``; :class:`CanonicalJob` es la proyección
normalizada de un empleo de la fuente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LocationScope(str, Enum):
    """Alcance geográfico canónico, clasificado solo a partir de ``locationRestrictions``."""

    EXPLICIT_EC = "explicit_ec"
    WORLDWIDE = "worldwide"
    OTHER_COUNTRY = "other_country"
    UNKNOWN = "unknown"


class RunStatus(str, Enum):
    """Resultado de una ejecución de recolección; una ejecución parcial nunca debe publicarse como completa."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class TimestampUnit(str, Enum):
    """Unidad detectada de un valor crudo de marca de tiempo Unix."""

    UNIX_SECONDS = "unix_seconds"
    UNIX_MILLISECONDS = "unix_milliseconds"
    UNKNOWN = "unknown"


class ObservationStatus(str, Enum):
    """Estado del ciclo de vida de una observación canónica de empleo."""

    ACTIVE = "active"
    EXPIRED = "expired"
    MISSING = "missing"
    INVALID = "invalid"


@dataclass
class RawPage:
    """Evidencia exacta en memoria de una página de API recolectada.

    ``body`` son los bytes exactos de la respuesta recibida; nada se recodifica.
    El adaptador sella ``run_status`` con el estado de la ejecución que
    produjo esta página cuando el snapshot se finaliza.
    """

    body: bytes
    request_params: dict
    status_code: int
    content_type: str | None
    sha256: str
    updated_at_raw: int | str | None
    updated_at_utc: datetime | None
    timestamp_unit: TimestampUnit
    total_count: int
    job_count: int
    offset: int
    captured_at: datetime
    run_status: RunStatus = RunStatus.PARTIAL


@dataclass(frozen=True)
class CanonicalJob:
    """Proyección normalizada de un empleo de la fuente; los valores crudos nunca se sobrescriben."""

    canonical_id: str
    source: str
    source_id: str
    source_url: str
    application_url: str
    snapshot_id: str
    title_raw: str
    company_raw: str
    company_slug_raw: str | None
    excerpt_raw: str | None
    description_html_raw: str
    location_restrictions_raw: list[str]
    location_scope: LocationScope
    timezone_restrictions_raw: list[int | float]
    employment_type_raw: str | None
    seniority_raw: list[str]
    categories_raw: list[str]
    salary_min_raw: int | float | None
    salary_max_raw: int | float | None
    salary_period_raw: str | None
    currency_raw: str | None
    published_at_raw: int | str | None
    published_at_utc: datetime | None
    expires_at_raw: int | str | None
    expires_at_utc: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    observation_status: ObservationStatus
    quality_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedPage:
    """Proyección de un payload de página validada en forma (antes del parseo de empleos)."""

    updated_at_raw: int | str | None
    updated_at_utc: datetime | None
    timestamp_unit: TimestampUnit
    total_count: int
    offset: int
    limit: int
    raw_jobs: tuple[object, ...]


@dataclass(frozen=True)
class Snapshot:
    """Una ejecución completa del adaptador; ``updatedAt`` vive aquí, nunca por empleo.

    ``raw_page_paths`` se conserva por compatibilidad de esquema con el
    contrato; la persistencia es un paso posterior, por lo que por ahora
    siempre está vacío y las páginas crudas en sí están disponibles en
    memoria vía ``raw_pages``.
    """

    snapshot_id: str
    source: str
    endpoint: str
    request_params: dict
    captured_at: datetime
    http_status: int
    content_type: str | None
    api_updated_at_raw: int | str | None
    api_updated_at_utc: datetime | None
    api_timestamp_unit: TimestampUnit
    total_count: int
    page_count: int
    job_count: int
    canonical_job_count: int
    duplicate_guid_count: int
    raw_page_paths: list[str]
    raw_page_sha256: list[str]
    run_status: RunStatus
    adapter_version: str
    quality_flags: list[str] = field(default_factory=list)
    jobs: tuple[CanonicalJob, ...] = ()
    raw_pages: tuple[RawPage, ...] = ()
