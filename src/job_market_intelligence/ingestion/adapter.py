"""Adaptador de recolección para la API de empleos remotos de Himalayas.

Mapeo del contrato (``docs/ingestion/himalayas-adapter-contract.md``):

- Solo se usa ``https://himalayas.app/jobs/api``, con ``limit=20`` y
  paginación por ``offset`` hasta cubrir ``totalCount``. Sin búsqueda por
  palabras clave.
- Cada respuesta exitosa se conserva como un :class:`RawPage` exacto en
  memoria (bytes, parámetros de la petición, estado, tipo de contenido,
  SHA-256, ``updatedAt`` de la fuente, conteo total); la persistencia a
  archivos crudos es un paso posterior, por lo que ``raw_page_paths``
  siempre está vacío.
- El adaptador realiza HTTP solo cuando se invoca
  :meth:`HimalayaAdapter.collect_complete_feed` o la ruta opt-in de página
  única :meth:`HimalayaAdapter.collect_and_persist_page` (exactamente una
  petición acotada, persistida a través de ``LocalCaptureStore``).
  Construirlo nunca toca la red. Pase un ``httpx.Client`` con un
  ``MockTransport`` (o un transporte simple) para pruebas sin conexión.
- Los fallos cierran en seco: respuestas no 2xx, JSON/forma malformados,
  marcas de tiempo de snapshot inverosímiles, firmas de página repetidas y
  cursores que no avanzan elevan subclases tipadas de
  :class:`HimalayasError` que portan el snapshot parcial; una identidad de
  empleo requerida ausente invalida el registro y el snapshot devuelto es
  ``partial``, nunca ``complete``.
- Interpretación resuelta por contrato: un cambio de ``totalCount`` o
  ``updatedAt`` durante una ejecución es un evento de calidad
  (``total_count_changed`` / ``api_updated_at_changed``), no un fallo; lo
  mismo aplica a la divergencia de unidad de marca de tiempo entre páginas.
- Los valores ``guid`` duplicados dentro de una colección colapsan en un
  único registro canónico (la primera observación gana; las posteriores
  actualizan ``last_seen_at``) mientras se conservan todas las páginas y
  observaciones crudas. No se reclama deduplicación entre fuentes.
- Atribución: cualquier exhibición de estos datos debe enlazar a
  ``ATTRIBUTION_URL``.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx

from .errors import HimalayasError, HimalayasHttpError, MalformedResponseError, PaginationError
from .models import CanonicalJob, ObservationStatus, RawPage, RunStatus, Snapshot, TimestampUnit
from .parser import SOURCE, parse_job, parse_page
from .storage import CaptureResult, LocalCaptureStore

ENDPOINT = "https://himalayas.app/jobs/api"
ATTRIBUTION_URL = "https://himalayas.app"
DEFAULT_LIMIT = 20
MAX_LIMIT = 20
ADAPTER_VERSION = "0.1.0"

#: Advertencia registrada en el manifiesto de cada captura acotada de
#: página única. Una página es evidencia, nunca un snapshot de feed
#: completo ni de mercado.
BOUNDED_SINGLE_PAGE_WARNING = (
    f"bounded_single_page_capture: exactly one page (limit={DEFAULT_LIMIT}, offset=0) was "
    "requested and persisted; this is not a complete-feed capture and no whole-market "
    "coverage is claimed"
)


@dataclass(frozen=True)
class PageCaptureResult:
    """Resultado tipado de una captura acotada opt-in de página única.

    ``page`` es la evidencia cruda exacta de la respuesta, ``capture`` es
    el recibo de persistencia (rutas deterministas, id de captura, SHA-256
    crudo) y los campos restantes son el sobre de atribución/versión
    registrado en el manifiesto. ``run_status`` siempre es ``partial``:
    una página nunca es un feed completo.
    """

    page: RawPage
    capture: CaptureResult
    source: str
    endpoint: str
    adapter_version: str
    attribution_url: str
    run_status: RunStatus
    warning: str


class HimalayaAdapter:
    """Pagina el feed completo de empleos remotos de Himalayas.

    El constructor acepta un ``httpx.Client`` listo (recomendado para
    pruebas, por ejemplo uno respaldado por ``httpx.MockTransport``) o un
    ``httpx.BaseTransport`` simple; si no se da ninguno, el adaptador crea
    su propio cliente. ``clock`` es inyectable para que las pruebas no
    dependan del reloj de pared.
    """

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if client is not None and transport is not None:
            raise ValueError("pase únicamente client o transport, no ambos")
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(transport=transport, timeout=30.0)
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)

    def close(self) -> None:
        """Cierra el cliente propio del adaptador (no-op cuando se inyectó un cliente)."""
        if self._owns_client:
            self._client.close()

    def collect_and_persist_page(self, *, store: LocalCaptureStore) -> PageCaptureResult:
        """Realiza exactamente una captura acotada de página y la persiste.

        Emite exactamente un GET de :data:`ENDPOINT` con ``limit=DEFAULT_LIMIT``
        y ``offset=0``, reutiliza el parseo de respuesta y la construcción de
        :class:`RawPage` existentes (se conservan los bytes exactos de la
        respuesta) y persiste la página vía
        :meth:`LocalCaptureStore.persist_page` con ``complete=False`` y
        :data:`BOUNDED_SINGLE_PAGE_WARNING`. Nunca pagina, no reintenta ni
        usa ``/jobs/api/search``, y nunca reclama un feed completo.

        Los fallos cierran en seco antes de cualquier escritura: los errores
        de petición/transporte y las respuestas no 2xx elevan
        :class:`HimalayasHttpError`, las respuestas malformadas elevan
        :class:`MalformedResponseError` (o :class:`TimestampError`), los
        desajustes de offset elevan :class:`PaginationError` y los rechazos
        de persistencia del almacén (por ejemplo :class:`OverwriteError`) se
        propagan sin cambios. No hay reintento automático.

        Devuelve un :class:`PageCaptureResult` que porta la página cruda, el
        recibo de persistencia y el sobre del manifiesto, para que quien
        llama pueda informar y verificar bytes/hash/manifiesto sin otra
        petición.
        """
        if not isinstance(store, LocalCaptureStore):
            raise TypeError(f"store debe ser un LocalCaptureStore; se obtuvo {type(store).__name__}")

        snapshot_id = uuid.uuid4().hex
        page, _records = self._collect_page(0, limit=DEFAULT_LIMIT, snapshot_id=snapshot_id)
        capture = store.persist_page(
            page,
            source=SOURCE,
            endpoint=ENDPOINT,
            attribution_url=ATTRIBUTION_URL,
            adapter_version=ADAPTER_VERSION,
            complete=False,
            warnings=(BOUNDED_SINGLE_PAGE_WARNING,),
        )
        return PageCaptureResult(
            page=page,
            capture=capture,
            source=SOURCE,
            endpoint=ENDPOINT,
            adapter_version=ADAPTER_VERSION,
            attribution_url=ATTRIBUTION_URL,
            run_status=RunStatus.PARTIAL,
            warning=BOUNDED_SINGLE_PAGE_WARNING,
        )

    def collect_complete_feed(self, *, limit: int = DEFAULT_LIMIT) -> Snapshot:
        """Recolecta todas las páginas del feed completo y devuelve un snapshot.

        Eleva un :class:`HimalayasError` tipado ante fallos a nivel de
        ejecución; el error porta el snapshot parcial cuando ya se
        recolectaron páginas.
        """
        if not isinstance(limit, int) or isinstance(limit, bool) or not 0 < limit <= MAX_LIMIT:
            raise ValueError(
                f"limit debe ser un entero entre 1 y {MAX_LIMIT} (el máximo documentado); se obtuvo {limit!r}"
            )

        snapshot_id = uuid.uuid4().hex
        pages: list[RawPage] = []
        records_by_key: dict[str, CanonicalJob] = {}
        quality_flags: list[str] = []
        duplicate_guid_count = 0
        offset = 0
        total_count: int | None = None
        api_updated_at_raw: int | str | None = None
        api_updated_at_utc: datetime | None = None
        api_unit = TimestampUnit.UNKNOWN

        try:
            while True:
                if total_count is not None and offset >= total_count:
                    break

                page, records = self._collect_page(offset, limit=limit, snapshot_id=snapshot_id)

                if pages and page.sha256 == pages[-1].sha256:
                    raise PaginationError(
                        f"firma de página repetida en offset={offset}; la API parece ignorar el parámetro offset"
                    )
                if page.job_count == 0 and page.total_count > 0:
                    raise PaginationError(
                        f"la página en offset={offset} no devolvió empleos; el cursor no puede avanzar"
                    )

                if total_count is None:
                    total_count = page.total_count
                elif page.total_count != total_count:
                    quality_flags.append("total_count_changed")

                if api_updated_at_raw is None:
                    api_updated_at_raw = page.updated_at_raw
                    api_updated_at_utc = page.updated_at_utc
                    api_unit = page.timestamp_unit
                elif page.updated_at_raw != api_updated_at_raw:
                    quality_flags.append("api_updated_at_changed")
                if (
                    api_unit is not TimestampUnit.UNKNOWN
                    and page.timestamp_unit is not TimestampUnit.UNKNOWN
                    and page.timestamp_unit is not api_unit
                ):
                    quality_flags.append("timestamp_unit_divergence")

                for record in records:
                    # Las entradas inválidas/ausentes no tienen guid utilizable
                    # y no deben deduplicarse entre sí.
                    key = record.source_id if record.source_id else f"__invalid_{len(records_by_key)}"
                    existing = records_by_key.get(key)
                    if existing is None:
                        records_by_key[key] = record
                    else:
                        duplicate_guid_count += 1
                        flags = (
                            existing.quality_flags
                            if "duplicate_guid" in existing.quality_flags
                            else [*existing.quality_flags, "duplicate_guid"]
                        )
                        records_by_key[key] = replace(existing, last_seen_at=record.last_seen_at, quality_flags=flags)

                pages.append(page)
                offset += page.job_count

            has_invalid = any(
                record.observation_status in (ObservationStatus.INVALID, ObservationStatus.MISSING)
                for record in records_by_key.values()
            )
            run_status = RunStatus.PARTIAL if has_invalid else RunStatus.COMPLETE
            return self._finalize_snapshot(
                snapshot_id=snapshot_id,
                pages=pages,
                records=records_by_key,
                quality_flags=quality_flags,
                run_status=run_status,
                total_count=total_count,
                api_updated_at_raw=api_updated_at_raw,
                api_updated_at_utc=api_updated_at_utc,
                api_unit=api_unit,
                duplicate_guid_count=duplicate_guid_count,
            )
        except HimalayasError as exc:
            if exc.snapshot is None and pages:
                run_status = RunStatus.PARTIAL if isinstance(exc, PaginationError) else RunStatus.FAILED
                exc.snapshot = self._finalize_snapshot(
                    snapshot_id=snapshot_id,
                    pages=pages,
                    records=records_by_key,
                    quality_flags=quality_flags,
                    run_status=run_status,
                    total_count=total_count,
                    api_updated_at_raw=api_updated_at_raw,
                    api_updated_at_utc=api_updated_at_utc,
                    api_unit=api_unit,
                    duplicate_guid_count=duplicate_guid_count,
                )
            raise

    def _collect_page(self, offset: int, *, limit: int, snapshot_id: str) -> tuple[RawPage, tuple[CanonicalJob, ...]]:
        """Obtiene y parsea una página; eleva errores tipados ante cualquier fallo."""
        request_params = {"limit": limit, "offset": offset}
        captured_at = self._clock()
        try:
            response = self._client.get(ENDPOINT, params=request_params)
        except httpx.HTTPError as exc:
            raise HimalayasHttpError(f"la petición falló para offset={offset}: {exc}") from exc
        if not 200 <= response.status_code < 300:
            raise HimalayasHttpError(f"respuesta no 2xx para offset={offset}: HTTP {response.status_code}")

        body = response.content
        content_type = response.headers.get("content-type")
        try:
            payload = response.json()
        except ValueError as exc:
            raise MalformedResponseError(f"cuerpo JSON inválido para offset={offset}") from exc

        parsed = parse_page(payload)
        if parsed.offset != offset:
            raise PaginationError(
                f"el offset de la respuesta ({parsed.offset}) no coincide con el offset solicitado ({offset})"
            )

        page = RawPage(
            body=body,
            request_params=request_params,
            status_code=response.status_code,
            content_type=content_type,
            sha256=hashlib.sha256(body).hexdigest(),
            updated_at_raw=parsed.updated_at_raw,
            updated_at_utc=parsed.updated_at_utc,
            timestamp_unit=parsed.timestamp_unit,
            total_count=parsed.total_count,
            job_count=len(parsed.raw_jobs),
            offset=offset,
            captured_at=captured_at,
        )
        records = tuple(
            parse_job(raw, snapshot_id=snapshot_id, captured_at=captured_at, expected_unit=parsed.timestamp_unit)
            for raw in parsed.raw_jobs
        )
        return page, records

    def _finalize_snapshot(
        self,
        *,
        snapshot_id: str,
        pages: list[RawPage],
        records: dict[str, CanonicalJob],
        quality_flags: list[str],
        run_status: RunStatus,
        total_count: int | None,
        api_updated_at_raw: int | str | None,
        api_updated_at_utc: datetime | None,
        api_unit: TimestampUnit,
        duplicate_guid_count: int,
    ) -> Snapshot:
        for page in pages:
            page.run_status = run_status
        last = pages[-1] if pages else None
        jobs = tuple(records.values())
        return Snapshot(
            snapshot_id=snapshot_id,
            source=SOURCE,
            endpoint=ENDPOINT,
            request_params=last.request_params if last else {"limit": DEFAULT_LIMIT, "offset": 0},
            captured_at=self._clock(),
            http_status=last.status_code if last else 0,
            content_type=last.content_type if last else None,
            api_updated_at_raw=api_updated_at_raw,
            api_updated_at_utc=api_updated_at_utc,
            api_timestamp_unit=api_unit,
            total_count=total_count or 0,
            page_count=len(pages),
            job_count=sum(page.job_count for page in pages),
            canonical_job_count=len(jobs),
            duplicate_guid_count=duplicate_guid_count,
            raw_page_paths=[],
            raw_page_sha256=[page.sha256 for page in pages],
            run_status=run_status,
            adapter_version=ADAPTER_VERSION,
            quality_flags=list(dict.fromkeys(quality_flags)),
            jobs=jobs,
            raw_pages=tuple(pages),
        )
