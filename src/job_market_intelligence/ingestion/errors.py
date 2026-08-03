"""Errores tipados del adaptador y el parser de Himalayas.

Cada error es una subclase de :class:`HimalayasError` y puede portar el
:class:`~job_market_intelligence.ingestion.models.Snapshot` parcial
recolectado antes del fallo, para que quien llama pueda distinguir un fallo
duro de una ejecución parcial sin publicar datos incompletos en silencio.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import guard for type checkers
    from .models import Snapshot


class HimalayasError(Exception):
    """Clase base de todos los errores del adaptador/parser.

    ``snapshot`` contiene la evidencia recolectada antes del fallo cuando se
    recolectó alguna página con éxito; en caso contrario es ``None``.
    """

    def __init__(self, message: str, *, snapshot: Snapshot | None = None) -> None:
        super().__init__(message)
        self.snapshot = snapshot


class HimalayasHttpError(HimalayasError):
    """Una petición falló (error de red) o devolvió una respuesta no 2xx."""


class MalformedResponseError(HimalayasError):
    """El cuerpo de la respuesta no es JSON válido o viola el contrato de forma de página."""


class PaginationError(HimalayasError):
    """La paginación no avanzó (página repetida, offset repetido o página vacía)."""


class TimestampError(HimalayasError):
    """Un valor de marca de tiempo es inverosímil o tiene un tipo/unidad no soportados."""
