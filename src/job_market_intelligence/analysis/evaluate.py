"""Comando offline: materializa el informe determinista de la evaluación de borrador.

``materialize_evaluation_report`` lee el conjunto de datos analítico EXISTENTE
(``data/analytics/development-sample-0.1.0.json``), el artefacto de taxonomía
versionado y el artefacto de evaluación de borrador confirmado
(``data/evaluation/skill-extraction-development-0.1.0.json``), valida el
contrato de evaluación (tipo de conjunto de datos, identidad de snapshot, versión
de taxonomía, forma de muestra, esquema de etiquetas, citas y offsets de evidencia
exactos), compara las etiquetas escritas a mano con las predicciones embebidas de
la línea base de palabras clave del conjunto de datos y escribe el informe
determinista:

    data/evaluation/skill-extraction-development-report-0.1.0.json

El artefacto de evaluación es la fuente de anotación de borrador versionada
(citas y offsets de inspección directa; no revisada por humanos ni gold). El
materializador verifica su serialización canónica byte por byte, de modo que
ambos artefactos son reproducibles: el informe se regenera de forma
determinista y un artefacto existente con contenido diferente se rechaza
(cierre ante fallos), nunca se sobrescribe. No se consultan páginas crudas,
manifiestos, respuestas de API ni red, y no se lee ningún reloj de pared.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .errors import DatasetError, EvaluationError
from .evaluation import (
    EVALUATION_ARTIFACT_DEFAULT_PATH,
    REPORT_ARTIFACT_DEFAULT_PATH,
    build_report,
    evaluation_from_dict,
    load_evaluation,
    serialize_evaluation,
    serialize_report,
)
from .taxonomy import TAXONOMY_ARTIFACT_DEFAULT_PATH, load_taxonomy

#: Default paths (run from the repository root).
DEFAULT_DATASET_PATH = "data/analytics/development-sample-0.1.0.json"
DEFAULT_TAXONOMY_PATH = TAXONOMY_ARTIFACT_DEFAULT_PATH
DEFAULT_EVALUATION_PATH = EVALUATION_ARTIFACT_DEFAULT_PATH
DEFAULT_REPORT_OUTPUT_PATH = REPORT_ARTIFACT_DEFAULT_PATH


def _read_json(path: str | Path, error_type: type[Exception], label: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise error_type(f"no se puede leer {label} {path}: {exc}") from exc
    except ValueError as exc:
        raise error_type(f"{label} {path} no es JSON válido: {exc}") from exc


def _write_atomic(path: Path, data: bytes) -> None:
    """Escritura atómica (temp en el mismo directorio + fsync + rename) con rechazo de contenido distinto."""
    if path.exists():
        if path.read_bytes() == data:
            return
        raise DatasetError(
            f"se rechaza sobrescribir {path} con contenido diferente; el informe es determinista "
            f"y debe eliminarse explícitamente antes de regenerarlo"
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


def materialize_evaluation_report(
    *,
    dataset_path: str | Path,
    taxonomy_path: str | Path,
    evaluation_path: str | Path,
    report_output_path: str | Path,
) -> Path:
    """Materializa el informe de evaluación determinista para el conjunto de borrador.

    Totalmente offline y determinista. Eleva :class:`EvaluationError` cuando el
    artefacto de evaluación o su contrato son inválidos y :class:`DatasetError`
    cuando la salida cambiaría el contenido existente.
    """
    dataset = _read_json(dataset_path, DatasetError, "dataset")
    taxonomy = load_taxonomy(taxonomy_path)

    evaluation_file = Path(evaluation_path)
    try:
        raw_text = evaluation_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"no se puede leer el artefacto de evaluación {evaluation_path}: {exc}") from exc
    try:
        doc = json.loads(raw_text)
    except ValueError as exc:
        raise EvaluationError(f"el artefacto de evaluación {evaluation_path} no es JSON válido: {exc}") from exc
    canonical = serialize_evaluation(doc).decode("utf-8")
    if raw_text != canonical:
        raise EvaluationError(
            f"el artefacto de evaluación {evaluation_path} no está serializado canónicamente; el "
            f"artefacto de borrador debe ser reproducible (claves ordenadas, sangría de 2 espacios, salto de línea final)"
        )

    evaluation = evaluation_from_dict(doc)
    report = build_report(evaluation, dataset, taxonomy)
    data = serialize_report(report)

    output = Path(report_output_path)
    _write_atomic(output, data)
    return output


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: ``uv run python -m job_market_intelligence.analysis.evaluate``."""
    parser = argparse.ArgumentParser(
        description=(
            "Materializa el informe determinista de la evaluación de borrador para la muestra "
            "de desarrollo (conjunto de datos + taxonomía + artefacto de evaluación de borrador). "
            "Totalmente offline y determinista."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET_PATH, help="ruta del JSON del conjunto de datos analítico")
    parser.add_argument("--taxonomy", default=DEFAULT_TAXONOMY_PATH, help="ruta del JSON del artefacto de taxonomía")
    parser.add_argument(
        "--evaluation",
        default=DEFAULT_EVALUATION_PATH,
        help="ruta del JSON del artefacto de evaluación de borrador (la fuente de anotación confirmada)",
    )
    parser.add_argument(
        "--report-output",
        default=DEFAULT_REPORT_OUTPUT_PATH,
        help="ruta de salida del artefacto de informe de evaluación",
    )
    args = parser.parse_args(argv)
    path = materialize_evaluation_report(
        dataset_path=args.dataset,
        taxonomy_path=args.taxonomy,
        evaluation_path=args.evaluation,
        report_output_path=args.report_output,
    )
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
