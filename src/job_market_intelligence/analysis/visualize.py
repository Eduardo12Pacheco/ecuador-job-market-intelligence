"""Comando offline: materializa el artefacto de análisis descriptivo y las
visualizaciones de línea base para el conjunto de datos de desarrollo versionado.

    ``materialize_descriptive_analysis`` lee el conjunto de datos analítico EXISTENTE
    (``data/analytics/development-sample-0.1.0.json``) y el artefacto de taxonomía
    versionado (usado únicamente como búsqueda de esquema id -> nombre/categoría
    canónicos), valida el contrato documentado de la muestra de desarrollo
    (tipo ``development_sample``, exactamente 20 registros, una página con
    ``limit=20``/``offset=0``, ``complete: false``, snapshot ``cap_0370798f7af4b0e3``,
    versión de taxonomía coincidente), computa las métricas deterministas a nivel de
    registro y escribe:

    - ``data/analytics/descriptive-development-sample-0.1.0.json`` — el artefacto de
      análisis (frecuencia de habilidades, cobertura por categoría, habilidades sin
      coincidencias, pares de coocurrencia sin orden, matriz de coocurrencia, resumen
      de calidad/frescura, salvaguardas);
    - ``data/analytics/visualizations/development-sample-0.1.0/`` — los gráficos SVG
      de línea base y la tabla Markdown de habilidades sin coincidencias.

    No se consultan páginas crudas, manifiestos, respuestas de API ni red, y no se
    lee ningún reloj de pared. La salida es determinista: re-ejecutar con entradas
    idénticas produce bytes idénticos; un artefacto existente con contenido
    diferente se rechaza (cierre ante fallos), nunca se sobrescribe.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .descriptive import build_descriptive_analysis, serialize_analysis
from .errors import DatasetError
from .taxonomy import TAXONOMY_ARTIFACT_DEFAULT_PATH, load_taxonomy
from .visualizations import build_visualizations

#: Default paths (run from the repository root).
DEFAULT_DATASET_PATH = "data/analytics/development-sample-0.1.0.json"
DEFAULT_TAXONOMY_PATH = TAXONOMY_ARTIFACT_DEFAULT_PATH
DEFAULT_ANALYSIS_OUTPUT_PATH = "data/analytics/descriptive-development-sample-0.1.0.json"
DEFAULT_VISUALIZATIONS_DIR = "data/analytics/visualizations/development-sample-0.1.0"


def _read_dataset(dataset_path: str | Path) -> dict:
    try:
        return json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetError(f"no se puede leer el conjunto de datos {dataset_path}: {exc}") from exc
    except ValueError as exc:
        raise DatasetError(f"el conjunto de datos {dataset_path} no es JSON válido: {exc}") from exc


def _write_atomic(path: Path, data: bytes) -> None:
    """Escritura atómica (temp en el mismo directorio + fsync + rename) con rechazo de contenido distinto."""
    if path.exists():
        if path.read_bytes() == data:
            return
        raise DatasetError(
            f"refusing to overwrite {path} with different content; the artifact is "
            f"deterministic and must be deleted explicitly before regeneration"
        )
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


def materialize_descriptive_analysis(
    *,
    dataset_path: str | Path,
    taxonomy_path: str | Path,
    analysis_output_path: str | Path,
    visualizations_dir: str | Path,
) -> tuple[Path, list[Path]]:
    """Materializa el artefacto de análisis y las visualizaciones de línea base.

    Totalmente offline y determinista. Eleva :class:`DatasetError` cuando la salida
    cambiaría el contenido existente y :class:`DescriptiveError` cuando el conjunto
    de datos no es la muestra de desarrollo documentada.
"""
    dataset = _read_dataset(dataset_path)
    taxonomy = load_taxonomy(taxonomy_path)
    analysis = build_descriptive_analysis(dataset, taxonomy)
    data = serialize_analysis(analysis)

    output = Path(analysis_output_path)
    _write_atomic(output, data)
    artifacts = build_visualizations(analysis, visualizations_dir)
    return output, artifacts


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: ``uv run python -m job_market_intelligence.analysis.visualize``."""
    parser = argparse.ArgumentParser(
        description=(
            "Materializa el artefacto de análisis descriptivo y las visualizaciones de "
            "línea base SVG/Markdown para el conjunto de datos de desarrollo. Totalmente "
            "offline y determinista."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET_PATH, help="ruta del JSON del conjunto de datos analítico")
    parser.add_argument("--taxonomy", default=DEFAULT_TAXONOMY_PATH, help="ruta del JSON del artefacto de taxonomía")
    parser.add_argument(
        "--analysis-output",
        default=DEFAULT_ANALYSIS_OUTPUT_PATH,
        help="ruta de salida del artefacto de análisis descriptivo",
    )
    parser.add_argument(
        "--visualizations-dir",
        default=DEFAULT_VISUALIZATIONS_DIR,
        help="directorio de salida de las visualizaciones de línea base",
    )
    args = parser.parse_args(argv)
    output, artifacts = materialize_descriptive_analysis(
        dataset_path=args.dataset,
        taxonomy_path=args.taxonomy,
        analysis_output_path=args.analysis_output,
        visualizations_dir=args.visualizations_dir,
    )
    print(f"wrote {output}")
    for path in artifacts:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
