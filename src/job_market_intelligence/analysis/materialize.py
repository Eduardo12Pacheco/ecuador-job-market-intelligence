"""Comando offline: materializa el conjunto de datos de desarrollo versionado desde una
captura local persistida (página cruda + manifiesto).

``materialize_development_dataset`` lee la página cruda existente referenciada por
el manifiesto, verifica la integridad (SHA-256 y consistencia manifiesto/payload),
parsea la proyección canónica con el momento de captura y la identidad de captura
persistidos, construye el conjunto de datos de desarrollo y el informe de calidad y
escribe el artefacto versionado. La muestra de desarrollo siempre es ``complete: false``:
un manifiesto que declare ``complete: true`` se rechaza (cierre ante fallos). Sin acceso
a red, sin reloj de pared, sin identidades de snapshot inventadas.

Las rutas por defecto (ejecutadas desde la raíz del repositorio) apuntan a la captura
acotada autorizada de una sola página documentada en
``docs/ingestion/himalayas-adapter-contract.md``:

- manifiesto: ``data/manifests/himalayas/jobs_api_6b8244a52a80/00000000.manifest.json``
- taxonomía: ``data/taxonomy/technical-skills-0.1.0.json``
- salida:    ``data/analytics/development-sample-0.1.0.json``

La salida es determinista: re-ejecutar el comando con entradas idénticas produce
bytes idénticos. Una salida existente nunca se reemplaza con contenido diferente
(cierre ante fallos); el contenido idéntico es un no-op.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..ingestion.models import CanonicalJob
from ..ingestion.parser import parse_job, parse_page
from .dataset import build_development_dataset, resolve_snapshot_id, serialize_dataset
from .errors import DatasetError, DatasetIntegrityError
from .taxonomy import TAXONOMY_ARTIFACT_DEFAULT_PATH, load_taxonomy

#: Identidades de captura en vivo documentadas (ver el contrato de ingesta y el README).
DEFAULT_MANIFEST_PATH = "data/manifests/himalayas/jobs_api_6b8244a52a80/00000000.manifest.json"
DEFAULT_TAXONOMY_PATH = TAXONOMY_ARTIFACT_DEFAULT_PATH
DEFAULT_OUTPUT_PATH = "data/analytics/development-sample-0.1.0.json"

#: El SHA-256 crudo documentado de la captura en vivo autorizada. Materializar una
#: captura distinta con otro hash es posible, pero el artefacto de desarrollo confirmado
#: se genera exactamente a partir de esta captura.
DOCUMENTED_CAPTURE_RAW_SHA256 = (
    "0370798f7af4b0e39ab92fd0d486577f58cdd415812e612d6b86657ac07ab101"
)


def _read_manifest(manifest_path: str | Path) -> dict:
    try:
        return json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetError(f"no se puede leer el manifiesto {manifest_path}: {exc}") from exc
    except ValueError as exc:
        raise DatasetError(f"el manifiesto {manifest_path} no es JSON válido: {exc}") from exc


def _read_and_verify_raw(manifest: Mapping[str, Any]) -> dict:
    """Lee la página cruda referenciada por el manifiesto y verifica con cierre ante fallos."""
    raw_relative = manifest.get("raw_file_path")
    if not isinstance(raw_relative, str) or not raw_relative:
        raise DatasetIntegrityError("el manifiesto no tiene 'raw_file_path' o es inválido")
    raw_path = Path(raw_relative)
    if not raw_path.exists():
        raise DatasetIntegrityError(
            f"no se encontró el archivo de captura cruda en {raw_relative} (resuelto relativo al "
            f"directorio de trabajo; ejecutar desde la raíz del repositorio)"
        )
    raw_bytes = raw_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if sha256 != manifest.get("raw_sha256"):
        raise DatasetIntegrityError(
            f"desajuste de SHA-256 para {raw_relative}: el manifiesto registra "
            f"{manifest.get('raw_sha256')!r}, calculado {sha256}"
        )
    try:
        return json.loads(raw_bytes)
    except ValueError as exc:
        raise DatasetIntegrityError(f"la captura cruda {raw_relative} no es JSON válido: {exc}") from exc


def _verify_manifest_payload(manifest: Mapping[str, Any], payload: dict) -> None:
    """Falla de forma cerrada cuando el manifiesto y la página cruda se contradicen."""
    parsed = parse_page(payload)
    for manifest_key, payload_key, label in (
        ("offset", parsed.offset, "offset"),
        ("limit", parsed.limit, "limit"),
        ("total_count", parsed.total_count, "totalCount"),
        ("returned_jobs", len(parsed.raw_jobs), "jobs length"),
        ("updated_at_raw", parsed.updated_at_raw, "updatedAt"),
    ):
        if manifest.get(manifest_key) != payload_key:
            raise DatasetIntegrityError(
                f"el manifiesto '{manifest_key}'={manifest.get(manifest_key)!r} contradice la página "
                f"cruda {label}={payload_key!r}"
            )
    return parsed


def _parse_canonical_projection(
    payload: dict, manifest: Mapping[str, Any], snapshot_id: str
) -> tuple[CanonicalJob, ...]:
    parsed = parse_page(payload)
    captured_at_raw = manifest.get("captured_at")
    try:
        captured_at = datetime.fromisoformat(str(captured_at_raw))
    except (TypeError, ValueError) as exc:
        raise DatasetIntegrityError(f"el 'captured_at' del manifiesto no es ISO 8601: {captured_at_raw!r}") from exc
    if captured_at.tzinfo is None:
        raise DatasetIntegrityError(
            f"el 'captured_at' del manifiesto es ingenuo en zona horaria: {captured_at_raw!r}"
        )
    return tuple(
        parse_job(
            raw,
            snapshot_id=snapshot_id,
            captured_at=captured_at,
            expected_unit=parsed.timestamp_unit,
        )
        for raw in parsed.raw_jobs
    )


def _write_atomic(path: Path, data: bytes) -> None:
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


def materialize_development_dataset(
    *,
    manifest_path: str | Path,
    taxonomy_path: str | Path,
    output_path: str | Path,
    snapshot_id: str | None = None,
) -> Path:
    """Materializa el conjunto de datos de desarrollo versionado desde una captura persistida.

    Totalmente offline y determinista. Eleva :class:`DatasetIntegrityError` ante
    contradicciones captura/manifiesto y :class:`DatasetError` cuando la salida
    cambiaría el contenido existente.
    """
    manifest = _read_manifest(manifest_path)
    payload = _read_and_verify_raw(manifest)
    _verify_manifest_payload(manifest, payload)

    resolved_id, _origin = resolve_snapshot_id(manifest, snapshot_id)
    jobs = _parse_canonical_projection(payload, manifest, resolved_id)
    taxonomy = load_taxonomy(taxonomy_path)
    dataset = build_development_dataset(
        jobs,
        manifest=manifest,
        taxonomy=taxonomy,
        snapshot_id=snapshot_id,
        manifest_path=str(manifest_path),
    )
    data = serialize_dataset(dataset)

    output = Path(output_path)
    if output.exists():
        if output.read_bytes() == data:
            return output
        raise DatasetError(
            f"se rechaza sobrescribir {output_path} con contenido diferente; el artefacto es "
            f"determinista y debe eliminarse explícitamente antes de regenerarlo"
        )
    _write_atomic(output, data)
    return output


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: ``uv run python -m job_market_intelligence.analysis.materialize``."""
    parser = argparse.ArgumentParser(
        description=(
            "Materializa el conjunto de datos analítico de desarrollo versionado desde una "
            "captura local persistida (página cruda + manifiesto). Totalmente offline y determinista."
        )
    )
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, help="ruta del JSON del manifiesto de captura")
    parser.add_argument("--taxonomy", default=DEFAULT_TAXONOMY_PATH, help="ruta del JSON del artefacto de taxonomía")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="ruta de salida del artefacto del conjunto de datos")
    parser.add_argument(
        "--snapshot-id",
        default=None,
        help="id de snapshot explícito (por defecto: el capture_id del manifiesto; nunca inventado)",
    )
    args = parser.parse_args(argv)
    path = materialize_development_dataset(
        manifest_path=args.manifest,
        taxonomy_path=args.taxonomy,
        output_path=args.output,
        snapshot_id=args.snapshot_id,
    )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
