"""Visualizaciones de referencia deterministas, solo con la biblioteca estándar.

Los gráficos SVG y las tablas Markdown se generan con formato de cadena plano:
sin biblioteca de trazado, de modo que el análisis central se mantiene sin
dependencias y la salida es determinista byte a byte. Cada artefacto:

- contiene SOLO etiquetas, métricas y metadatos: nunca descripciones completas
  de ofertas crudas (``description_html_raw``) ni ningún otro texto crudo de oferta;
- incluye metadatos visibles en el pie de página además de un bloque ``<metadata>``
  incrustado con origen/atribución, el tipo ``development_sample``, el id de snapshot,
  la versión de taxonomía, la advertencia de 20 registros/una página y la salvaguarda
  de no representatividad de mercado;
- se regenera con bytes idénticos a partir de la misma entrada de análisis.

Artefactos (bajo ``data/analytics/visualizations/development-sample-0.1.0/``):

- ``skill-frequency.svg`` — gráfico de barras de cada habilidad coincidente (registros);
- ``category-coverage.svg`` — gráfico de barras de registros distintos por categoría;
- ``cooccurrence-matrix.svg`` — mapa de calor simétrico sobre ids de habilidad
  ordenados (diagonal cero, sin autopares);
- ``zero-match-skills.md`` — tabla legible de las habilidades de la taxonomía con cero
  coincidencias, con la distinción explícita de ``no_evidence``.

Las escrituras fallan con cierre: un artefacto existente con contenido diferente se
rechaza (``DatasetError``) en lugar de sobrescribirse en silencio.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from .errors import DatasetError

#: Métricas del lienzo SVG compartidas por los gráficos de barras.
_BAR_WIDTH = 1100
_BAR_HEIGHT = 560
_PLOT_X0 = 64
_PLOT_X1 = 1040
_PLOT_Y0 = 58
_PLOT_Y1 = 396

_FOOTER_FIRST_Y = 420
_FOOTER_STEP = 14


def _short_id(skill_id: str) -> str:
    """Elimina el prefijo ``skill.`` para las etiquetas de los ejes (los ids siguen canónicos en los datos)."""
    return skill_id.split(".", 1)[-1]


def _metadata_block(analysis: Mapping[str, Any]) -> str:
    meta = {
        "analysis_kind": analysis["analysis_kind"],
        "analysis_version": analysis["analysis_version"],
        "source": analysis["source"],
        "attribution_url": analysis["attribution_url"],
        "dataset_kind": analysis["dataset_kind"],
        "sample": analysis["sample"],
        "snapshot_id": analysis["snapshot_id"],
        "taxonomy_version": analysis["taxonomy_version"],
        "matcher_version": analysis["matcher_version"],
        "guardrails": analysis["guardrails"],
        "streamlit_status": analysis["streamlit_status"],
    }
    payload = json.dumps(meta, ensure_ascii=True, sort_keys=True)
    return f"<metadata>{xml_escape(payload)}</metadata>"


def _footer_lines(analysis: Mapping[str, Any]) -> list[str]:
    sample = analysis["sample"]
    return [
        f"source: {analysis['source']} | attribution: {analysis['attribution_url']}",
        f"dataset: {analysis['dataset_kind']} | {sample['records']} records | one page "
        f"(limit={sample['limit']}, offset={sample['offset']}) | complete: false",
        f"snapshot: {analysis['snapshot_id']} | taxonomy: {analysis['taxonomy_version']} "
        f"| matcher: {analysis['matcher_version']}",
        "warning: bounded single-page development sample — descriptive keyword evidence only",
        "guardrail: NOT market coverage, NOT correlation, NOT causality, NOT representative",
    ]


def _footer_svg(lines: Sequence[str]) -> str:
    texts = []
    for index, line in enumerate(lines):
        y = _FOOTER_FIRST_Y + index * _FOOTER_STEP
        texts.append(
            f'<text x="20" y="{y}" font-family="monospace" font-size="9.5" fill="#374151">{xml_escape(line)}</text>'
        )
    return "".join(texts)


def _nice_step(max_value: int) -> int:
    for step in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
        if max_value <= step * 5:
            return step
    return 1000


def _bar_chart_svg(
    *,
    title: str,
    subtitle: str,
    items: Sequence[tuple[str, int]],
    y_axis_label: str,
    analysis: Mapping[str, Any],
) -> bytes:
    """Un gráfico de barras determinista (SVG de la biblioteca estándar)."""
    values = [value for _, value in items]
    max_value = max(values) if values else 1
    step = _nice_step(max_value)
    y_max = max(step, ((max_value + step - 1) // step) * step)
    plot_h = _PLOT_Y1 - _PLOT_Y0
    n = len(items)
    slot = (_PLOT_X1 - _PLOT_X0) / n if n else 1
    bar_w = min(34, slot * 0.62)
    rotate = n > 12

    elements = [f"<title>{xml_escape(title)}</title>"]
    elements.append(
        f'<text x="20" y="24" font-family="sans-serif" font-size="16" font-weight="bold" '
        f'fill="#111827">{xml_escape(title)}</text>'
    )
    elements.append(
        f'<text x="20" y="42" font-family="sans-serif" font-size="11" fill="#4b5563">{xml_escape(subtitle)}</text>'
    )

    # Líneas de cuadrícula y etiquetas del eje Y.
    for tick in range(0, y_max + 1, step):
        y = _PLOT_Y1 - (tick / y_max) * plot_h
        elements.append(
            f'<line x1="{_PLOT_X0}" y1="{y:.1f}" x2="{_PLOT_X1}" y2="{y:.1f}" '
            f'stroke="#d1d5db" stroke-width="1" stroke-dasharray="3,3"/>'
        )
        elements.append(
            f'<text x="{_PLOT_X0 - 6}" y="{y + 3:.1f}" font-family="sans-serif" '
            f'font-size="9" fill="#6b7280" text-anchor="end">{tick}</text>'
        )
    elements.append(
        f'<text x="{_PLOT_X0 - 6}" y="{_PLOT_Y0 - 8}" font-family="sans-serif" '
        f'font-size="9.5" fill="#4b5563" text-anchor="end">{xml_escape(y_axis_label)}</text>'
    )

    for index, (label, value) in enumerate(items):
        x_center = _PLOT_X0 + slot * (index + 0.5)
        bar_h = (value / y_max) * plot_h
        y_bar = _PLOT_Y1 - bar_h
        elements.append(
            f'<rect x="{x_center - bar_w / 2:.1f}" y="{y_bar:.1f}" width="{bar_w:.1f}" '
            f'height="{bar_h:.1f}" fill="#2563eb" stroke="#1d4ed8" stroke-width="0.5">'
            f"<title>{xml_escape(label)}: {value} {y_axis_label}</title></rect>"
        )
        elements.append(
            f'<text x="{x_center:.1f}" y="{y_bar - 5:.1f}" font-family="sans-serif" '
            f'font-size="9" fill="#111827" text-anchor="middle">{value}</text>'
        )
        if rotate:
            elements.append(
                f'<text x="{x_center:.1f}" y="{_PLOT_Y1 + 12}" font-family="sans-serif" '
                f'font-size="8" fill="#374151" text-anchor="start" '
                f'transform="rotate(-45 {x_center:.1f} {_PLOT_Y1 + 12})">{xml_escape(label)}</text>'
            )
        else:
            elements.append(
                f'<text x="{x_center:.1f}" y="{_PLOT_Y1 + 16}" font-family="sans-serif" '
                f'font-size="9" fill="#374151" text-anchor="middle">{xml_escape(label)}</text>'
            )

    elements.append(_footer_svg(_footer_lines(analysis)))
    elements.append(_metadata_block(analysis))

    body = "".join(elements)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_BAR_WIDTH}" height="{_BAR_HEIGHT}" '
        f'viewBox="0 0 {_BAR_WIDTH} {_BAR_HEIGHT}">'
        f'<rect width="{_BAR_WIDTH}" height="{_BAR_HEIGHT}" fill="#ffffff"/>'
        f"{body}</svg>\n"
    )
    return svg.encode("utf-8")


def svg_skill_frequency(analysis: Mapping[str, Any]) -> bytes:
    """Gráfico de barras de cada habilidad coincidente, ordenado por recuento de registros (desc) y luego por id."""
    items = [(skill_id, count) for skill_id, count in analysis["skill_frequency"].items() if count > 0]
    items.sort(key=lambda item: (-item[1], item[0]))
    chart_items = [(_short_id(skill_id), count) for skill_id, count in items]
    return _bar_chart_svg(
        title="Skill frequency — development sample",
        subtitle=(
            "distinct records per skill (a skill counts at most once per record); "
            "labels are skill identifiers without the 'skill.' prefix"
        ),
        items=chart_items,
        y_axis_label="records",
        analysis=analysis,
    )


def svg_category_coverage(analysis: Mapping[str, Any]) -> bytes:
    """Gráfico de barras de registros distintos por categoría (definición en el artefacto)."""
    categories = analysis["category_coverage"]["categories"]
    chart_items = [(entry["category"], entry["records"]) for entry in categories]
    return _bar_chart_svg(
        title="Category coverage — development sample",
        subtitle=(
            "distinct records with at least one matched skill in the category "
            "(counted at most once per record per category)"
        ),
        items=chart_items,
        y_axis_label="records",
        analysis=analysis,
    )


def _heat_color(count: int, max_count: int) -> str:
    if count <= 0:
        return "#f1f5f9"
    t = count / max_count
    r = round(219 + (30 - 219) * t)
    g = round(234 + (58 - 234) * t)
    b = round(254 + (138 - 254) * t)
    return f"rgb({r},{g},{b})"


def svg_cooccurrence_matrix(analysis: Mapping[str, Any]) -> bytes:
    """Mapa de calor simétrico sobre ids de habilidad ordenados (diagonal cero, sin autopares)."""
    matrix_doc = analysis["cooccurrence_matrix"]
    skill_ids = matrix_doc["skill_ids"]
    matrix = matrix_doc["matrix"]
    n = len(skill_ids)
    cell = 14
    grid = n * cell
    left = 84
    top = 104
    max_count = max(max(row) for row in matrix) if matrix else 0
    width = left + grid + 16 + 14 + 46
    height = top + grid + 40 + 5 * _FOOTER_STEP + 12

    elements = ["<title>Cooccurrence matrix — development sample</title>"]
    elements.append(
        '<text x="20" y="24" font-family="sans-serif" font-size="16" font-weight="bold" '
        'fill="#111827">Cooccurrence matrix — development sample</text>'
    )
    elements.append(
        f'<text x="20" y="42" font-family="sans-serif" font-size="11" fill="#4b5563">'
        f"symmetric matrix over all {n} taxonomy skills (sorted ids); each cell counts "
        f"distinct records containing both skills; diagonal = 0 (no self-pairs)</text>"
    )

    # Etiquetas de fila (izquierda) y de columna (arriba, rotadas -90).
    for i, skill_id in enumerate(skill_ids):
        y = top + i * cell + cell / 2 + 3
        elements.append(
            f'<text x="{left - 8}" y="{y:.1f}" font-family="monospace" font-size="8" '
            f'fill="#374151" text-anchor="end">{xml_escape(_short_id(skill_id))}</text>'
        )
    for j, skill_id in enumerate(skill_ids):
        x = left + j * cell + cell / 2
        elements.append(
            f'<text x="{x:.1f}" y="{top - 10}" font-family="monospace" font-size="7" '
            f'fill="#374151" text-anchor="start" '
            f'transform="rotate(-90 {x:.1f} {top - 10})">{xml_escape(_short_id(skill_id))}</text>'
        )

    # Celdas con tooltips.
    for i, row in enumerate(matrix):
        for j, count in enumerate(row):
            x = left + j * cell
            y = top + i * cell
            elements.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{_heat_color(count, max_count)}">'
                f"<title>{xml_escape(_short_id(skill_ids[i]))} x "
                f"{xml_escape(_short_id(skill_ids[j]))}: {count} records</title></rect>"
            )

    # Leyenda.
    legend_x = left + grid + 16
    legend_y = top + 60
    legend_h = 200
    elements.append(
        '<defs><linearGradient id="heat-gradient" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1e3a8a"/><stop offset="100%" stop-color="#dbeafe"/>'
        "</linearGradient></defs>"
    )
    elements.append(
        f'<rect x="{legend_x}" y="{legend_y}" width="14" height="{legend_h}" '
        f'fill="url(#heat-gradient)" stroke="#9ca3af" stroke-width="0.5"/>'
    )
    for label, fy in (
        ("0", legend_y + legend_h),
        (str(max_count // 2), legend_y + legend_h // 2),
        (str(max_count), legend_y),
    ):
        elements.append(
            f'<text x="{legend_x + 20}" y="{fy + 3}" font-family="sans-serif" '
            f'font-size="9" fill="#374151">{label}</text>'
        )
    elements.append(
        f'<text x="{legend_x}" y="{legend_y - 8}" font-family="sans-serif" font-size="9" fill="#4b5563">records</text>'
    )
    elements.append(
        f'<text x="20" y="{top + grid + 24}" font-family="sans-serif" font-size="9.5" '
        f'fill="#4b5563">matrix cell [i][j] = number of distinct records containing both '
        f"skills; values match the cooccurrence-pairs artifact exactly.</text>"
    )

    footer_y = top + grid + 40
    footer = "".join(
        f'<text x="20" y="{footer_y + index * _FOOTER_STEP}" font-family="monospace" '
        f'font-size="9.5" fill="#374151">{xml_escape(line)}</text>'
        for index, line in enumerate(_footer_lines(analysis))
    )
    elements.append(footer)
    elements.append(_metadata_block(analysis))

    body = "".join(elements)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
        f"{body}</svg>\n"
    )
    return svg.encode("utf-8")


def zero_match_markdown(analysis: Mapping[str, Any]) -> bytes:
    """Tabla Markdown legible para las habilidades de la taxonomía con cero coincidencias."""
    zero = analysis["zero_match_skills"]
    sample = analysis["sample"]
    lines = [
        "# Zero-match taxonomy skills — development sample",
        "",
        f"- source: {analysis['source']} | attribution: {analysis['attribution_url']}",
        f"- dataset: {analysis['dataset_kind']} | {sample['records']} records | one page "
        f"(limit={sample['limit']}, offset={sample['offset']}) | complete: false",
        f"- snapshot: {analysis['snapshot_id']} | taxonomy: {analysis['taxonomy_version']} "
        f"| matcher: {analysis['matcher_version']}",
        "- analysis: descriptive keyword evidence only (see "
        "`descriptive-development-sample-0.1.0.json` under `data/analytics/`)",
        "- warning: bounded single-page development sample — NOT market coverage, "
        "NOT correlation, NOT causality, NOT representative",
        f"- streamlit: {analysis['streamlit_status']}",
        "",
        "A taxonomy skill with **zero matches in this sample** is **not evidence** that "
        "jobs lack the skill: it means the deterministic keyword baseline found no "
        "occurrence of the skill's terms in the searched fields of any of the 20 records. "
        "This is distinct from `no_evidence` records (records where the taxonomy found no "
        "keyword at all). This sample has 0 `no_evidence` records and "
        f"{zero['count']} zero-match skills.",
        "",
        "| skill_id | name | category | matched_records |",
        "|---|---|---|---|",
    ]
    for skill in zero["skills"]:
        lines.append(f"| {skill['skill_id']} | {skill['name']} | {skill['category']} | {skill['matched_records']} |")
    lines += [
        "",
        f"Summary: {zero['count']} of the {len(analysis['cooccurrence_matrix']['skill_ids'])} "
        "taxonomy skills have zero matches in this development sample.",
        "",
    ]
    text = "\n".join(lines)
    return text.encode("utf-8")


def _write_artifact(path: Path, data: bytes) -> None:
    """Escritura atómica con cierre ante fallo: se niega a reemplazar contenido existente."""
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


def build_visualizations(analysis: Mapping[str, Any], out_dir: str | Path) -> list[Path]:
    """Escribe todos los artefactos de visualización de referencia; devuelve sus rutas ordenadas.

    Determinista y con cierre ante fallo: un artefacto existente con contenido
    diferente lanza :class:`DatasetError` en lugar de sobrescribirse.
    """
    directory = Path(out_dir)
    artifacts = [
        ("skill-frequency.svg", svg_skill_frequency(analysis)),
        ("category-coverage.svg", svg_category_coverage(analysis)),
        ("cooccurrence-matrix.svg", svg_cooccurrence_matrix(analysis)),
        ("zero-match-skills.md", zero_match_markdown(analysis)),
    ]
    paths: list[Path] = []
    for name, data in artifacts:
        path = directory / name
        _write_artifact(path, data)
        paths.append(path)
    return sorted(paths)
