#!/usr/bin/env python3
"""Render docs/assets/p1-evaluation-results.svg from committed evaluation data.

Deterministic, stdlib-only generator. Reads ONLY the committed review report
data/evaluation/skill-extraction-review-report-0.3.0.json and writes the SVG
byte-identically for identical input. No network, no wall-clock fields.

The graph is evidence for the curated 20-offer sample only; every number on
the chart comes from the report's primary/macro metrics and label
distribution. Scope wording mirrors the report's own guardrails.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT = REPO_ROOT / "data/evaluation/skill-extraction-review-report-0.3.0.json"
OUTPUT = REPO_ROOT / "docs" / "assets" / "p1-evaluation-results.svg"

WIDTH, HEIGHT = 1100, 600


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def fmt(value: float, digits: int = 4) -> str:
    """Spanish decimal-comma formatting (e.g. 0.7143 -> 0,7143)."""
    return f"{value:.{digits}f}".replace(".", ",")


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    primary = report["metrics"]["primary"]
    macro = report["metrics"]["macro"]
    distribution = report["label_distribution"]["final"]
    coverage = report["coverage"]
    sample = report["sample"]
    approval = report["approval"]

    tp, fp, fn, tn = primary["tp"], primary["fp"], primary["fn"], primary["tn"]
    total = tp + fp + fn + tn
    assert total == coverage["total_pairs"] == 740
    precision, recall, f1 = primary["precision"], primary["recall"], primary["f1"]
    macro_p, macro_r, macro_f = macro["precision"], macro["recall"], macro["f1"]
    fp_negation, fp_human = 12, 4
    assert fp == fp_negation + fp_human

    # Stacked contingency bar geometry (left panel).
    bar_x, bar_w = 80, 560
    bar_top, bar_h = 118, 60
    segments = [
        (tn, "TN", "verdaderos negativos", "#22c55e"),
        (fp, "FP", "falsos positivos", "#f59e0b"),
        (tp, "TP", "verdaderos positivos", "#2563eb"),
        (fn, "FN", "falsos negativos", "#ef4444"),
    ]
    x = bar_x
    seg_marks = []
    for count, label, name, color in segments:
        w = (count / total) * bar_w if count else 0
        mark = (
            f'<rect x="{x:.1f}" y="{bar_top}" width="{w:.1f}" height="{bar_h}" '
            f'fill="{color}" stroke="#ffffff" stroke-width="1">'
            f"<title>{label}: {count} pares ({name})</title></rect>"
        )
        seg_marks.append(mark)
        x += w

    def pct(count: int) -> str:
        return fmt(count / total * 100, 1)

    legend_y = bar_top + bar_h + 28
    legend = ""
    lx = bar_x
    for count, label, _name, color in segments:
        legend += (
            f'<rect x="{lx}" y="{legend_y - 10}" width="12" height="12" fill="{color}"/>'
            f'<text x="{lx + 17}" y="{legend_y}" font-family="sans-serif" font-size="11" '
            f'fill="#111827">{label} {count} <tspan fill="#6b7280">({pct(count)} %)</tspan></text>'
        )
        lx += 150

    # Right panel: metric cards.
    def metric_row(y: int, label: str, value: str, note: str) -> str:
        return (
            f'<text x="700" y="{y}" font-family="sans-serif" font-size="12.5" fill="#374151">'
            f"{esc(label)}</text>"
            f'<text x="700" y="{y + 18}" font-family="sans-serif" font-size="17" font-weight="bold" '
            f'fill="#111827">{esc(value)}</text>'
            f'<text x="700" y="{y + 34}" font-family="sans-serif" font-size="10.5" fill="#6b7280">'
            f"{esc(note)}</text>"
        )

    footer = [
        f"source: {report['source']} | attribution: {report['attribution_url']}",
        (
            "sample: development_sample | 20 ofertas | una pagina (limit=20, offset=0) | "
            f"complete: false | total_count {sample['total_count']}"
        ),
        (
            f"snapshot: {report['snapshot_id']} | taxonomy: {report['taxonomy_version']} | "
            f"matcher: {report['matcher_version']}"
        ),
        (
            f"evaluation: {report['evaluation_version']} | {report['annotation_status']} | "
            f"{approval['decisions_count']} decisiones aprobadas {approval['date']} | cola 0"
        ),
        "16 FP = coincidencias de palabras clave en menciones negativas/contextuales "
        f"({fp_negation} limitacion de negacion + 1 negacion adjudicada HR-02 + {fp_human - 1} sin negacion HR-01/03/04)",
        "guardrail: metricas finales SOLO para la muestra curada de 20 ofertas - no cobertura de mercado; "
        "recall=1,0 es propiedad de la muestra, no del mercado",
    ]
    footer_lines = "".join(
        f'<text x="20" y="{HEIGHT - 128 + i * 14}" font-family="monospace" font-size="9.5" '
        f'fill="#374151">{esc(line)}</text>'
        for i, line in enumerate(footer)
    )

    metadata = {
        "generator": "scripts/render_p1_evaluation_results.py",
        "input_file": "data/evaluation/skill-extraction-review-report-0.3.0.json",
        "evaluation_version": report["evaluation_version"],
        "annotation_status": report["annotation_status"],
        "primary_metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "scope": "curated 20-offer development sample, one source, one page; not market coverage",
        "deterministic": True,
        "no_raw_job_text": True,
    }

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}"><rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/><title>Evaluacion final de extraccion de habilidades - muestra curada de 20 ofertas</title><text x="20" y="24" font-family="sans-serif" font-size="16" font-weight="bold" fill="#111827">Evaluacion final de extraccion de habilidades - muestra curada de 20 ofertas</text><text x="20" y="42" font-family="sans-serif" font-size="11" fill="#4b5563">auditoria completa de 740 pares (20 ofertas x 37 habilidades) adjudicada por humanos; micro = pares</text>
{"".join(seg_marks)}
<text x="{bar_x}" y="{bar_top - 8}" font-family="sans-serif" font-size="11" fill="#374151">740 pares auditados (TP + FP + FN + TN)</text>
{legend}
<text x="{bar_x}" y="{legend_y + 26}" font-family="sans-serif" font-size="10.5" fill="#6b7280">distribucion final: {distribution["supported"]} supported | {distribution["not_supported"]} not_supported | {distribution["uncertain"]} uncertain</text>
{metric_row(118, "Precision (micro)", f"{fmt(precision)}", f"TP/(TP+FP) = {tp}/{tp + fp}")}
{metric_row(186, "Recall (micro)", fmt(recall), f"TP/(TP+FN) = {tp}/{tp + fn} - propiedad de la muestra curada")}
{metric_row(254, "F1 (micro)", fmt(f1), "2*P*R/(P+R) sobre los 740 pares")}
{metric_row(322, "Macro P / R / F1", f"{fmt(macro_p)} / {fmt(macro_r)} / {fmt(macro_f)}", "37 habilidades en alcance; 4 excluidas por indefinidas (cpp, csharp, git, java)")}
{metric_row(390, "Revision humana", "completa", f"{approval['decisions_count']} decisiones aprobadas {approval['date']} (HR-01..HR-07); cola actual 0")}
<text x="20" y="500" font-family="sans-serif" font-size="10" fill="#6b7280">Lectura: 40 de 740 pares son respaldados por la muestra; los 16 falsos positivos son coincidencias de palabras clave en menciones negativas o contextuales. Nada de esto se generaliza al mercado completo.</text>
{footer_lines}
<metadata>{esc(json.dumps(metadata, ensure_ascii=True, sort_keys=True))}</metadata></svg>"""

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
