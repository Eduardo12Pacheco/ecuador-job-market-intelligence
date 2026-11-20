"""Comando offline: materializa la revisión determinista de segunda pasada.

``materialize_second_pass_review`` lee el conjunto de datos analítico EXISTENTE
(``data/analytics/development-sample-0.1.0.json``), el artefacto de taxonomía
versionado y el artefacto de evaluación del primer borrador
(``data/evaluation/skill-extraction-development-0.1.0.json``), construye las
etiquetas independientes de la segunda pasada a partir del manifiesto de
adjudicación curado (``analysis/second_pass.py`` — las predicciones del matcher
nunca se consultan al etiquetar), valida el contrato completo de revisión
20 x 37, compara la segunda pasada contra el primer borrador y contra las
predicciones embebidas de la línea base de palabras clave del conjunto de datos,
y escribe los dos artefactos deterministas:

    data/evaluation/skill-extraction-review-0.2.0.json
    data/evaluation/skill-extraction-review-report-0.2.0.json

Ambos artefactos declaran ``annotation_status: draft_second_pass`` y
``human_review_required: true``; NO son gold y NO están revisados por humanos.
La generación es determinista y de cierre ante fallos: un artefacto existente
con contenido diferente se rechaza (nunca se sobrescribe), y no se consultan
páginas crudas, manifiestos, respuestas de API ni red. No se lee ningún reloj
de pared.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import DatasetError
from .evaluate import _write_atomic
from .evaluation import EVALUATION_ARTIFACT_DEFAULT_PATH, load_evaluation
from .second_pass import (
    REVIEW_ARTIFACT_DEFAULT_PATH,
    REVIEW_REPORT_DEFAULT_PATH,
    build_second_pass_doc,
    build_second_pass_report,
    second_pass_from_dict,
    serialize_second_pass,
    serialize_second_pass_report,
    validate_second_pass,
)
from .taxonomy import TAXONOMY_ARTIFACT_DEFAULT_PATH, load_taxonomy

#: Default paths (run from the repository root).
DEFAULT_DATASET_PATH = "data/analytics/development-sample-0.1.0.json"
DEFAULT_TAXONOMY_PATH = TAXONOMY_ARTIFACT_DEFAULT_PATH
DEFAULT_FIRST_PASS_PATH = EVALUATION_ARTIFACT_DEFAULT_PATH
DEFAULT_ARTIFACT_OUTPUT_PATH = REVIEW_ARTIFACT_DEFAULT_PATH
DEFAULT_REPORT_OUTPUT_PATH = REVIEW_REPORT_DEFAULT_PATH


def _read_json(path: str | Path, error_type: type[Exception], label: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise error_type(f"no se puede leer {label} {path}: {exc}") from exc
    except ValueError as exc:
        raise error_type(f"{label} {path} no es JSON válido: {exc}") from exc


def materialize_second_pass_review(
    *,
    dataset_path: str | Path,
    taxonomy_path: str | Path,
    first_pass_path: str | Path,
    artifact_output_path: str | Path,
    report_output_path: str | Path,
) -> Path:
    """Materializa el artefacto y el informe de la revisión de segunda pasada.

    Totalmente offline y determinista. Eleva :class:`EvaluationError` cuando el
    contrato de revisión es inválido (incluida cualquier afirmación de gold o
    revisión humana) y :class:`DatasetError` cuando una salida cambiaría el
    contenido existente.
    """
    dataset = _read_json(dataset_path, DatasetError, "dataset")
    taxonomy = load_taxonomy(taxonomy_path)
    first_pass = load_evaluation(first_pass_path)  # validates draft_evaluation status

    doc = build_second_pass_doc(dataset, taxonomy)
    second_pass = second_pass_from_dict(doc)
    validate_second_pass(second_pass, dataset, taxonomy)
    report = build_second_pass_report(first_pass, second_pass, dataset, taxonomy)

    artifact_out = Path(artifact_output_path)
    _write_atomic(artifact_out, serialize_second_pass(doc))
    report_out = Path(report_output_path)
    _write_atomic(report_out, serialize_second_pass_report(report))
    return report_out


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: ``uv run python -m job_market_intelligence.analysis.review``."""
    parser = argparse.ArgumentParser(
        description=(
            "Materializa la revisión determinista de etiquetas de habilidades de segunda "
            "pasada para la muestra de desarrollo (conjunto de datos + taxonomía + evaluación "
            "del primer borrador). Totalmente offline y determinista; el artefacto es "
            "draft_second_pass con human_review_required: true."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET_PATH, help="ruta del JSON del conjunto de datos analítico")
    parser.add_argument("--taxonomy", default=DEFAULT_TAXONOMY_PATH, help="ruta del JSON del artefacto de taxonomía")
    parser.add_argument(
        "--first-pass",
        default=DEFAULT_FIRST_PASS_PATH,
        help="ruta del JSON del artefacto de evaluación del primer borrador",
    )
    parser.add_argument(
        "--artifact-output",
        default=DEFAULT_ARTIFACT_OUTPUT_PATH,
        help="ruta de salida del artefacto de revisión de segunda pasada",
    )
    parser.add_argument(
        "--report-output",
        default=DEFAULT_REPORT_OUTPUT_PATH,
        help="ruta de salida del informe de revisión de segunda pasada",
    )
    args = parser.parse_args(argv)
    report_path = materialize_second_pass_review(
        dataset_path=args.dataset,
        taxonomy_path=args.taxonomy,
        first_pass_path=args.first_pass,
        artifact_output_path=args.artifact_output,
        report_output_path=args.report_output,
    )
    print(f"wrote {args.artifact_output}")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
