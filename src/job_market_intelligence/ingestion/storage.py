"""Persistencia local acotada de páginas crudas de API y manifiestos de recolección.

Este módulo es la capa de disco detrás de la regla de *evidencia cruda* del
contrato de ingesta (``docs/ingestion/himalayas-adapter-contract.md``): los
bytes exactos de la respuesta de una página recolectada se almacenan
verbatim, y cada página almacenada tiene un pequeño manifiesto JSON que
registra metadatos de petición/respuesta sin reemplazar la evidencia cruda.

Reglas de diseño:

- La persistencia es **opt-in y acotada**. Nada de aquí toca la red y nada
  se ejecuta implícitamente: quien llama pasa un
  :class:`~job_market_intelligence.ingestion.models.RawPage` ya recolectado
  a :meth:`LocalCaptureStore.persist_page` y decide qué almacenar.
- Los bytes crudos se escriben exactamente como se recibieron
  (``RawPage.body``); nunca se parsean, reserializan, ordenan, normalizan ni
  truncan.
- Las rutas son deterministas y relativas al repositorio:
  ``<root>/<source>/<endpoint-component>_<endpoint-hash>/<offset>.json``. El
  componente legible del endpoint mantiene rutas amigables; el SHA-256
  estable de 12 hex del endpoint previene colisiones entre endpoints que
  comparten un componente legible; los offsets se rellenan con ceros a 8
  dígitos.
- Las escrituras son atómicas por archivo (archivo temporal del mismo
  directorio + fsync + ``os.replace``). Un archivo crudo o manifiesto
  existente nunca se sobrescribe: una ruta determinista repetida falla con
  :class:`OverwriteError`.
- Los manifiestos son sidecars JSON UTF-8 pequeños, nombrados
  deterministamente junto a la clave de ruta cruda, que contienen solo
  metadatos (sin objetos de cliente, headers, credenciales ni rutas
  absolutas). Los parámetros de petición con información sensible se
  redactan antes de la serialización.
- Los fallos cierran en seco: páginas no 2xx, desajustes de SHA-256, páginas
  malformadas y marcas de tiempo naive se rechazan antes de escribir nada.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from .models import RawPage, TimestampUnit

DEFAULT_RAW_ROOT = "data/raw"
DEFAULT_MANIFEST_ROOT = "data/manifests"
MANIFEST_VERSION = 1

# Las claves de parámetros de petición que contienen alguno de estos
# fragmentos se tratan como portadoras de secretos y sus valores se redactan
# en los manifiestos.
_SECRET_KEY_FRAGMENTS = ("token", "secret", "password", "authorization", "api_key", "apikey")
_REDACTED = "[REDACTED]"


class StorageError(Exception):
    """Clase base de los fallos de persistencia de captura local."""


class OverwriteError(StorageError):
    """Un destino determinista de crudo/manifiesto ya existe; se rechaza reemplazarlo."""


class IntegrityError(StorageError):
    """La página cruda suministrada falló una verificación de integridad (por ejemplo, desajuste de SHA-256)."""


@dataclass(frozen=True)
class CaptureResult:
    """Resultado tipado de una llamada exitosa a :meth:`LocalCaptureStore.persist_page`.

    ``raw_file_path_relative`` y ``manifest_file_path_relative`` son rutas
    POSIX relativas al repositorio (nunca absolutas, nunca escapan del
    directorio de trabajo) y son los valores registrados dentro del
    manifiesto.
    """

    raw_file_path: Path
    manifest_path: Path
    raw_file_path_relative: str
    manifest_file_path_relative: str
    capture_id: str
    raw_sha256: str


class LocalCaptureStore:
    """Escribe páginas crudas exactas y manifiestos JSON bajo raíces configuradas.

    Las raíces son por defecto ``data/raw`` y ``data/manifests`` relativas al
    directorio de trabajo. Las raíces relativas mantienen los manifiestos
    relativos al repositorio por construcción; una raíz absoluta fuera del
    directorio de trabajo se rechaza porque sus rutas de manifiesto no
    podrían seguir siendo relativas al repositorio.
    """

    def __init__(
        self,
        *,
        raw_root: str | Path = DEFAULT_RAW_ROOT,
        manifest_root: str | Path = DEFAULT_MANIFEST_ROOT,
    ) -> None:
        self.raw_root = Path(raw_root)
        self.manifest_root = Path(manifest_root)

    def persist_page(
        self,
        raw_page: RawPage,
        *,
        source: str,
        endpoint: str,
        attribution_url: str,
        adapter_version: str,
        complete: bool = False,
        warnings: tuple[str, ...] = (),
        errors: tuple[str, ...] = (),
        capture_id: str | None = None,
    ) -> CaptureResult:
        """Persiste una página cruda y su manifiesto; eleva errores ante cualquier rechazo.

        ``complete`` es la declaración de quien llama sobre cuán acotada es
        esta captura; cualquier ``errors`` fuerza ``complete: false``. Eleva
        :class:`OverwriteError` cuando el destino determinista de crudo o
        manifiesto ya existe, :class:`IntegrityError` ante un desajuste de
        SHA-256, :class:`StorageError` para capturas no 2xx o no
        serializables, y :class:`ValueError` para argumentos malformados.
        Cuando se eleva un error, nada se escribe.
        """
        source = _validate_path_component(source, "source")
        for label, value in (
            ("endpoint", endpoint),
            ("attribution_url", attribution_url),
            ("adapter_version", adapter_version),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{label} debe ser una cadena no vacía")

        if not isinstance(raw_page, RawPage):
            raise TypeError(f"raw_page debe ser un RawPage; se obtuvo {type(raw_page).__name__}")
        body = raw_page.body
        if not isinstance(body, bytes):
            raise ValueError("raw_page.body debe ser bytes")
        if isinstance(raw_page.status_code, bool) or not isinstance(raw_page.status_code, int):
            raise ValueError("raw_page.status_code debe ser un entero")
        if not 200 <= raw_page.status_code < 300:
            raise StorageError(
                f"se rechaza persistir una captura no 2xx: HTTP {raw_page.status_code}"
            )
        offset = raw_page.offset
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("raw_page.offset debe ser un entero no negativo")
        for label, value in (
            ("total_count", raw_page.total_count),
            ("job_count", raw_page.job_count),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"raw_page.{label} debe ser un entero")
        _require_utc(raw_page.captured_at, "captured_at")
        if raw_page.updated_at_utc is not None:
            _require_utc(raw_page.updated_at_utc, "updated_at_utc")

        sha256 = hashlib.sha256(body).hexdigest()
        if not isinstance(raw_page.sha256, str) or raw_page.sha256 != sha256:
            raise IntegrityError(
                f"desajuste de SHA-256 para {source}/{endpoint}: se suministró "
                f"{raw_page.sha256!r}, se calculó {sha256}"
            )

        request_params, redacted = _sanitize_request_params(raw_page.request_params)
        if not _json_serializable(request_params):
            raise StorageError("request_params contiene valores que no se pueden serializar a JSON")

        limit = request_params.get("limit")
        if isinstance(limit, bool) or not isinstance(limit, int):
            limit = None

        warnings_list = [str(warning) for warning in warnings]
        errors_list = [str(error) for error in errors]
        if redacted:
            warnings_list.append("secret_request_params_redacted")
        complete = bool(complete) and not errors_list

        if capture_id is None:
            capture_id = f"cap_{sha256[:16]}"
        if not isinstance(capture_id, str) or not capture_id:
            raise ValueError("capture_id debe ser una cadena no vacía")

        endpoint_component = _endpoint_component(endpoint)
        endpoint_hash = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:12]
        directory = f"{endpoint_component}_{endpoint_hash}"
        stem = PurePosixPath(source) / directory / f"{offset:08d}"
        raw_path = self.raw_root / stem.with_suffix(".json")
        manifest_path = self.manifest_root / stem.with_suffix(".manifest.json")

        raw_relative = _repo_relative(raw_path)
        manifest_relative = _repo_relative(manifest_path)

        existing = []
        if raw_path.exists():
            existing.append("raw")
        if manifest_path.exists():
            existing.append("manifest")
        if existing:
            raise OverwriteError(
                f"se rechaza sobrescribir la captura existente de {' y '.join(existing)} en "
                f"{stem}: las rutas deterministas son inmutables"
            )

        unit = raw_page.timestamp_unit
        timestamp_unit = unit.value if isinstance(unit, TimestampUnit) else str(unit)
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "capture_id": capture_id,
            "source": source,
            "endpoint": endpoint,
            "request_params": request_params,
            "offset": offset,
            "limit": limit,
            "http_status": raw_page.status_code,
            "content_type": raw_page.content_type,
            "captured_at": _utc_iso(raw_page.captured_at),
            "updated_at_raw": raw_page.updated_at_raw,
            "updated_at_utc": _utc_iso(raw_page.updated_at_utc) if raw_page.updated_at_utc is not None else None,
            "timestamp_unit": timestamp_unit,
            "total_count": raw_page.total_count,
            "returned_jobs": raw_page.job_count,
            "raw_file_path": raw_relative,
            "raw_sha256": sha256,
            "adapter_version": adapter_version,
            "attribution_url": attribution_url,
            "complete": complete,
            "warnings": warnings_list,
            "errors": errors_list,
        }
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

        self._write_atomic(raw_path, body)
        try:
            self._write_atomic(manifest_path, manifest_bytes)
        except BaseException:
            # El archivo crudo ya se movió a su lugar; se elimina para que una
            # captura a medio persistir nunca sobreviva a una escritura de
            # manifiesto fallida.
            raw_path.unlink(missing_ok=True)
            raise

        return CaptureResult(
            raw_file_path=raw_path,
            manifest_path=manifest_path,
            raw_file_path_relative=raw_relative,
            manifest_file_path_relative=manifest_relative,
            capture_id=capture_id,
            raw_sha256=sha256,
        )

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        """Escribe ``data`` en ``path`` atómicamente vía temp del mismo directorio + fsync + replace."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise


def _validate_path_component(value: str, label: str) -> str:
    """Rechaza valores que podrían escapar o estructurar la ruta de almacenamiento."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} debe ser una cadena no vacía")
    if value in (".", "..") or "/" in value or "\\" in value:
        raise ValueError(f"{label} debe ser un componente de ruta seguro único; se obtuvo {value!r}")
    return value


def _endpoint_component(endpoint: str) -> str:
    """Componente legible derivado de la ruta para una URL de endpoint."""
    parsed = urlparse(endpoint)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        segments = [parsed.netloc or "endpoint"]
    component = "_".join(_sanitize_segment(segment) for segment in segments)
    return component or "endpoint"


def _sanitize_segment(segment: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", segment)
    return cleaned.strip("_") or "x"


def _repo_relative(path: Path) -> str:
    """Ruta POSIX relativa al directorio de trabajo; cierra en seco ante escapes."""
    if path.is_absolute():
        try:
            relative = path.relative_to(Path.cwd())
        except ValueError as exc:
            raise StorageError(
                f"refusing to record an absolute path in a manifest: {path} is outside "
                f"the working directory {Path.cwd()}"
            ) from exc
    else:
        relative = path
    return PurePosixPath(relative).as_posix()


def _require_utc(value: datetime, label: str) -> None:
    """Rechaza marcas de tiempo naive en lugar de escribir hora local en silencio."""
    if value.tzinfo is None:
        raise ValueError(f"{label} debe ser consciente de zona horaria; se rechaza escribir una marca de tiempo naive")


def _utc_iso(value: datetime) -> str:
    """Serializa una marca de tiempo como UTC ISO 8601, convirtiendo valores locales conscientes."""
    return value.astimezone(timezone.utc).isoformat()


def _sanitize_request_params(params: dict | None) -> tuple[dict, bool]:
    """Redacta valores de parámetros de petición portadores de secretos; conserva el resto."""
    if params is None:
        raise ValueError("raw_page.request_params debe ser un dict, no None")
    if not isinstance(params, dict):
        raise ValueError(
            f"raw_page.request_params debe ser un dict; se obtuvo {type(params).__name__}"
        )
    cleaned: dict = {}
    redacted = False
    for key, value in params.items():
        if not isinstance(key, str):
            key = str(key)
        lowered = key.lower()
        if any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS):
            cleaned[key] = _REDACTED
            redacted = True
        else:
            cleaned[key] = value
    return cleaned, redacted


def _json_serializable(value: object) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True
