"""Parseo y normalización de páginas de la API de Himalayas.

Notas de comportamiento (mapeo del contrato de
``docs/ingestion/himalayas-adapter-contract.md``):

- ``locationRestrictions`` es la única evidencia geográfica. Una lista
  explícitamente vacía significa ``worldwide``; los valores ausentes/nulos/
  malformados permanecen como ``unknown`` y nunca se coercionan a una lista
  vacía. Las restricciones de zona horaria se conservan pero nunca se usan
  para clasificar el alcance.
- Las marcas de tiempo se parsean defensivamente: los valores de 10 dígitos
  son segundos Unix, los de 13 dígitos son milisegundos Unix, y cualquier
  otra cosa es inverosímil y eleva :class:`TimestampError` en lugar de
  interpretarse en silencio. ``None`` es un nulo tolerado (el contrato
  permite valores de marca de tiempo nulos).
- Un campo requerido ausente marca el registro y lo señala como ``invalid``;
  el registro se conserva con su evidencia cruda, nunca se rellena con un
  valor inferido.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from .errors import MalformedResponseError, TimestampError
from .models import CanonicalJob, LocationScope, ObservationStatus, ParsedPage, TimestampUnit

SOURCE = "himalayas"

# Bandas documentadas de marcas de tiempo Unix. El fixture porta segundos
# de 10 dígitos mientras la documentación publicada menciona milisegundos,
# así que ambas bandas son válidas; los valores de 9/11/12/14 dígitos quedan
# fuera de ambas bandas y se rechazan como inverosímiles.
SECONDS_MIN = 1_000_000_000
SECONDS_MAX = 9_999_999_999
MILLISECONDS_MIN = 1_000_000_000_000
MILLISECONDS_MAX = 9_999_999_999_999

# Campos canónicos requeridos cuya ausencia invalida el registro.
_INVALIDATING_FLAGS = frozenset(
    {
        "missing_guid",
        "missing_application_link",
        "missing_title",
        "missing_company",
        "missing_description",
        "missing_location_restrictions",
        "malformed_location_restrictions",
    }
)


def detect_timestamp_unit(value: int) -> TimestampUnit:
    """Detecta segundos vs. milisegundos para un valor entero de marca de tiempo."""
    if SECONDS_MIN <= value <= SECONDS_MAX:
        return TimestampUnit.UNIX_SECONDS
    if MILLISECONDS_MIN <= value <= MILLISECONDS_MAX:
        return TimestampUnit.UNIX_MILLISECONDS
    raise TimestampError(
        f"marca de tiempo unix inverosímil {value!r}: fuera de las bandas soportadas "
        f"de segundos de 10 dígitos y milisegundos de 13 dígitos"
    )


def parse_unix_timestamp(value: Any) -> tuple[datetime | None, TimestampUnit]:
    """Parsea un valor crudo de marca de tiempo a UTC, detectando su unidad.

    Acepta enteros y cadenas numéricas; ``None`` se asigna a ``(None, unknown)``.
    Los valores inverosímiles o no soportados elevan :class:`TimestampError`.
    """
    if value is None:
        return None, TimestampUnit.UNKNOWN
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TimestampError(
            f"tipo de marca de tiempo no soportado {type(value).__name__}: {value!r}; "
            f"se esperaba un entero o una cadena numérica"
        )
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise TimestampError(f"marca de tiempo no numérica {value!r}") from exc
    unit = detect_timestamp_unit(numeric)
    if unit is TimestampUnit.UNIX_MILLISECONDS:
        numeric //= 1000
    return datetime.fromtimestamp(numeric, tz=UTC), unit


def classify_location_scope(value: Any) -> LocationScope:
    """Clasifica ``locationRestrictions`` según la tabla del contrato."""
    if value is None or not isinstance(value, list):
        return LocationScope.UNKNOWN
    if len(value) == 0:
        return LocationScope.WORLDWIDE
    for item in value:
        if isinstance(item, str) and item.strip().lower() == "ecuador":
            return LocationScope.EXPLICIT_EC
    return LocationScope.OTHER_COUNTRY


def canonical_id_for(source_id: str) -> str:
    """SHA-256 determinista de ``source`` + ``source_id``."""
    digest = hashlib.sha256()
    digest.update(f"{SOURCE}\0{source_id}".encode())
    return digest.hexdigest()


def _require_int(payload: dict, key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MalformedResponseError(f"el campo de paginación requerido {key!r} falta o no es un entero: {value!r}")
    return value


def parse_page(payload: Any) -> ParsedPage:
    """Valida un payload de página y proyecta sus metadatos requeridos.

    Eleva :class:`MalformedResponseError` ante violaciones de forma y
    :class:`TimestampError` ante un ``updatedAt`` de nivel superior
    inverosímil.
    """
    if not isinstance(payload, dict):
        raise MalformedResponseError(f"el payload de la respuesta no es un objeto JSON: {type(payload).__name__}")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        raise MalformedResponseError(f"el campo requerido 'jobs' no es una lista: {type(jobs).__name__}")
    total_count = _require_int(payload, "totalCount")
    offset = _require_int(payload, "offset")
    limit = _require_int(payload, "limit")

    updated_at_raw = payload.get("updatedAt")
    if updated_at_raw is None:
        updated_at_utc, timestamp_unit = None, TimestampUnit.UNKNOWN
    elif isinstance(updated_at_raw, bool) or not isinstance(updated_at_raw, (int, str)):
        raise MalformedResponseError(
            f"el 'updatedAt' de nivel superior tiene tipo no soportado {type(updated_at_raw).__name__}: "
            f"{updated_at_raw!r}"
        )
    else:
        updated_at_utc, timestamp_unit = parse_unix_timestamp(updated_at_raw)

    return ParsedPage(
        updated_at_raw=updated_at_raw,
        updated_at_utc=updated_at_utc,
        timestamp_unit=timestamp_unit,
        total_count=total_count,
        offset=offset,
        limit=limit,
        raw_jobs=tuple(jobs),
    )


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _parse_job_timestamp(
    raw: dict,
    key: str,
    flags: list[str],
    expected_unit: TimestampUnit | None,
) -> tuple[Any, datetime | None]:
    """Parsea una marca de tiempo de empleo; ausente/nula se tolera, inverosímil se marca."""
    value = raw.get(key)
    if value is None:
        return None, None
    try:
        parsed, unit = parse_unix_timestamp(value)
    except TimestampError:
        flags.append(f"implausible_timestamp:{key}")
        return value, None
    if (
        expected_unit is not None
        and expected_unit is not TimestampUnit.UNKNOWN
        and unit is not expected_unit
        and unit is not TimestampUnit.UNKNOWN
    ):
        flags.append(f"timestamp_unit_divergence:{key}")
    return value, parsed


def parse_job(
    raw: Any,
    *,
    snapshot_id: str,
    captured_at: datetime,
    expected_unit: TimestampUnit | None = None,
) -> CanonicalJob:
    """Normaliza una entrada cruda de empleo en un registro canónico.

    Nunca eleva errores por problemas de datos dentro de un empleo: los
    campos requeridos ausentes y las marcas de tiempo inverosímiles se marcan
    y el registro se señala como ``invalid`` (o ``missing`` para una entrada
    que no es dict), lo que el adaptador refleja como snapshot parcial.
    """
    if not isinstance(raw, dict):
        return CanonicalJob(
            canonical_id=canonical_id_for(""),
            source=SOURCE,
            source_id="",
            source_url="",
            application_url="",
            snapshot_id=snapshot_id,
            title_raw="",
            company_raw="",
            company_slug_raw=None,
            excerpt_raw=None,
            description_html_raw="",
            location_restrictions_raw=[],
            location_scope=LocationScope.UNKNOWN,
            timezone_restrictions_raw=[],
            employment_type_raw=None,
            seniority_raw=[],
            categories_raw=[],
            salary_min_raw=None,
            salary_max_raw=None,
            salary_period_raw=None,
            currency_raw=None,
            published_at_raw=None,
            published_at_utc=None,
            expires_at_raw=None,
            expires_at_utc=None,
            first_seen_at=captured_at,
            last_seen_at=captured_at,
            observation_status=ObservationStatus.MISSING,
            quality_flags=["malformed_job_entry"],
        )

    flags: list[str] = []

    def required_str(key: str, flag: str) -> str:
        value = raw.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            flags.append(flag)
            return ""
        return value if isinstance(value, str) else str(value)

    source_id_raw = raw.get("guid")
    if not isinstance(source_id_raw, str) or not source_id_raw.strip():
        flags.append("missing_guid")
        source_id = ""
        source_url = ""
    else:
        source_id = source_id_raw
        # Himalayas devuelve actualmente la URL del anuncio como guid; se
        # mantienen como campos canónicos separados porque fuentes futuras
        # pueden diferir.
        source_url = source_id

    application_url = required_str("applicationLink", "missing_application_link")
    title_raw = required_str("title", "missing_title")
    company_raw = required_str("companyName", "missing_company")
    description_html_raw = required_str("description", "missing_description")

    location_raw = raw.get("locationRestrictions")
    if location_raw is None:
        flags.append("missing_location_restrictions")
        location_restrictions_raw: list[str] = []
        location_scope = LocationScope.UNKNOWN
    elif not isinstance(location_raw, list):
        flags.append("malformed_location_restrictions")
        location_restrictions_raw = []
        location_scope = LocationScope.UNKNOWN
    else:
        location_scope = classify_location_scope(location_raw)
        location_restrictions_raw = [item if isinstance(item, str) else str(item) for item in location_raw]

    timezone_raw = raw.get("timezoneRestrictions")
    timezone_restrictions_raw: list[int | float] = (
        [item for item in timezone_raw if isinstance(item, (int, float)) and not isinstance(item, bool)]
        if isinstance(timezone_raw, list)
        else []
    )

    published_at_raw, published_at_utc = _parse_job_timestamp(raw, "pubDate", flags, expected_unit)
    expires_at_raw, expires_at_utc = _parse_job_timestamp(raw, "expiryDate", flags, expected_unit)

    def optional_number(key: str) -> int | float | None:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return value

    def optional_list(key: str) -> list:
        value = raw.get(key)
        return value if isinstance(value, list) else []

    invalid = any(flag in _INVALIDATING_FLAGS or flag.startswith("implausible_timestamp:") for flag in flags)
    if invalid:
        observation_status = ObservationStatus.INVALID
    elif expires_at_utc is not None and expires_at_utc <= captured_at:
        observation_status = ObservationStatus.EXPIRED
    else:
        observation_status = ObservationStatus.ACTIVE

    return CanonicalJob(
        canonical_id=canonical_id_for(source_id),
        source=SOURCE,
        source_id=source_id,
        source_url=source_url,
        application_url=application_url,
        snapshot_id=snapshot_id,
        title_raw=title_raw,
        company_raw=company_raw,
        company_slug_raw=_as_optional_str(raw.get("companySlug")),
        excerpt_raw=_as_optional_str(raw.get("excerpt")),
        description_html_raw=description_html_raw,
        location_restrictions_raw=location_restrictions_raw,
        location_scope=location_scope,
        timezone_restrictions_raw=timezone_restrictions_raw,
        employment_type_raw=_as_optional_str(raw.get("employmentType")),
        seniority_raw=[str(item) for item in optional_list("seniority") if isinstance(item, str)],
        categories_raw=[str(item) for item in optional_list("categories") if isinstance(item, str)],
        salary_min_raw=optional_number("minSalary"),
        salary_max_raw=optional_number("maxSalary"),
        salary_period_raw=_as_optional_str(raw.get("salaryPeriod")),
        currency_raw=_as_optional_str(raw.get("currency")),
        published_at_raw=published_at_raw,
        published_at_utc=published_at_utc,
        expires_at_raw=expires_at_raw,
        expires_at_utc=expires_at_utc,
        first_seen_at=captured_at,
        last_seen_at=captured_at,
        observation_status=observation_status,
        quality_flags=flags,
    )
