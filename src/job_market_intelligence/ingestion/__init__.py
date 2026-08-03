"""Adaptador de ingesta de Himalayas: API pública.

Superficie tipada pequeña: un adaptador de recolección, ayudantes de parseo,
objetos de valor, errores tipados y persistencia local acotada de crudos y
manifiestos. Ver ``docs/ingestion/himalayas-adapter-contract.md``.
"""

from .adapter import (
    ADAPTER_VERSION,
    ATTRIBUTION_URL,
    BOUNDED_SINGLE_PAGE_WARNING,
    DEFAULT_LIMIT,
    ENDPOINT,
    HimalayaAdapter,
    PageCaptureResult,
)
from .errors import (
    HimalayasError,
    HimalayasHttpError,
    MalformedResponseError,
    PaginationError,
    TimestampError,
)
from .models import (
    CanonicalJob,
    LocationScope,
    ObservationStatus,
    ParsedPage,
    RawPage,
    RunStatus,
    Snapshot,
    TimestampUnit,
)
from .parser import (
    SOURCE,
    canonical_id_for,
    classify_location_scope,
    parse_job,
    parse_page,
    parse_unix_timestamp,
)
from .storage import (
    DEFAULT_MANIFEST_ROOT,
    DEFAULT_RAW_ROOT,
    CaptureResult,
    IntegrityError,
    LocalCaptureStore,
    OverwriteError,
    StorageError,
)

__all__ = [
    "ADAPTER_VERSION",
    "ATTRIBUTION_URL",
    "BOUNDED_SINGLE_PAGE_WARNING",
    "CanonicalJob",
    "CaptureResult",
    "DEFAULT_LIMIT",
    "DEFAULT_MANIFEST_ROOT",
    "DEFAULT_RAW_ROOT",
    "ENDPOINT",
    "HimalayaAdapter",
    "HimalayasError",
    "HimalayasHttpError",
    "IntegrityError",
    "LocalCaptureStore",
    "LocationScope",
    "MalformedResponseError",
    "ObservationStatus",
    "OverwriteError",
    "PaginationError",
    "ParsedPage",
    "PageCaptureResult",
    "RawPage",
    "RunStatus",
    "SOURCE",
    "Snapshot",
    "StorageError",
    "TimestampError",
    "TimestampUnit",
    "canonical_id_for",
    "classify_location_scope",
    "parse_job",
    "parse_page",
    "parse_unix_timestamp",
]
