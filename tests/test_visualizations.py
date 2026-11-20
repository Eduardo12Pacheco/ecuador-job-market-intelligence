"""Pruebas offline de las visualizaciones de línea base deterministas y del CLI.

Los artefactos se generan solo con la biblioteca estándar (generación de SVG
como cadena + tablas Markdown); no se requiere ninguna dependencia de
graficado ni se agrega ninguna. Cada artefacto debe:

- ser byte-determinista entre generaciones repetidas;
- llevar metadatos visibles/incrustados (fuente, atribución, versión de
  taxonomía, instantánea, ``development_sample``, la advertencia de
  20 registros/una página y la salvaguarda de no representatividad de
  mercado);
- contener SOLO etiquetas, métricas y metadatos — nunca el texto crudo
  completo de las descripciones de empleo ni las claves de los campos crudos.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from job_market_intelligence.analysis.descriptive import build_descriptive_analysis
from job_market_intelligence.analysis.errors import AnalysisError, DatasetError
from job_market_intelligence.analysis.taxonomy import (
    TAXONOMY_ARTIFACT_DEFAULT_PATH,
    load_taxonomy,
)
from job_market_intelligence.analysis.visualizations import (
    build_visualizations,
    svg_category_coverage,
    svg_cooccurrence_matrix,
    svg_skill_frequency,
    zero_match_markdown,
)
from job_market_intelligence.analysis.visualize import (
    DEFAULT_ANALYSIS_OUTPUT_PATH,
    DEFAULT_DATASET_PATH,
    DEFAULT_TAXONOMY_PATH,
    DEFAULT_VISUALIZATIONS_DIR,
    main,
    materialize_descriptive_analysis,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPO_ROOT / "data" / "analytics" / "development-sample-0.1.0.json"
TAXONOMY_PATH = REPO_ROOT / TAXONOMY_ARTIFACT_DEFAULT_PATH

EXPECTED_ARTIFACTS = [
    "category-coverage.svg",
    "cooccurrence-matrix.svg",
    "skill-frequency.svg",
    "zero-match-skills.md",
]

# Claves de campos crudos que nunca deben aparecer dentro de los artefactos generados.
_RAW_KEYS = (b"description_html_raw", b"title_raw", b"excerpt_raw", b"categories_raw")


@pytest.fixture(scope="session")
def analysis() -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return build_descriptive_analysis(dataset, load_taxonomy(TAXONOMY_PATH))


@pytest.fixture(scope="session")
def raw_description_text(analysis) -> str:
    # La descripción HTML cruda completa del primer registro: prohibida en los artefactos.
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return dataset["records"][0]["description_html_raw"]


class TestSvgArtifacts:
    def test_all_artifacts_generated(self, analysis, tmp_path) -> None:
        out = tmp_path / "viz"
        paths = build_visualizations(analysis, out)
        assert sorted(p.name for p in paths) == EXPECTED_ARTIFACTS
        for path in paths:
            assert path.exists()
            assert path.stat().st_size > 0

    def test_svg_contains_visible_metadata(self, analysis) -> None:
        for svg in (
            svg_skill_frequency(analysis),
            svg_category_coverage(analysis),
            svg_cooccurrence_matrix(analysis),
        ):
            text = svg.decode("utf-8")
            assert "https://himalayas.app" in text
            assert "technical-skills-0.1.0" in text
            assert "cap_0370798f7af4b0e3" in text
            assert "development_sample" in text
            assert "one page" in text
            assert "complete: false" in text
            assert "not market" in text
            assert "<metadata>" in text

    def test_svg_has_embedded_metadata_json(self, analysis) -> None:
        svg = svg_skill_frequency(analysis).decode("utf-8")
        start = svg.index("<metadata>") + len("<metadata>")
        end = svg.index("</metadata>")
        meta = json.loads(svg[start:end])
        assert meta["source"] == "himalayas"
        assert meta["attribution_url"] == "https://himalayas.app"
        assert meta["snapshot_id"] == "cap_0370798f7af4b0e3"
        assert meta["taxonomy_version"] == "technical-skills-0.1.0"
        assert meta["dataset_kind"] == "development_sample"
        assert meta["sample"]["records"] == 20
        assert meta["sample"]["complete"] is False
        assert any("not market" in g for g in meta["guardrails"])

    def test_skill_frequency_bars_reflect_metrics(self, analysis) -> None:
        svg = svg_skill_frequency(analysis).decode("utf-8")
        # Barra superior: skill.ai con 19 registros; la etiqueta y el valor están presentes.
        assert ">ai<" in svg
        assert ">19<" in svg

    def test_heatmap_contains_all_skill_ids(self, analysis) -> None:
        svg = svg_cooccurrence_matrix(analysis).decode("utf-8")
        ids = analysis["cooccurrence_matrix"]["skill_ids"]
        assert len(ids) == 37
        assert "machine_learning" in svg
        assert "python" in svg

    def test_svg_is_well_formed_xml(self, analysis) -> None:
        import xml.etree.ElementTree as ET

        for svg in (
            svg_skill_frequency(analysis),
            svg_category_coverage(analysis),
            svg_cooccurrence_matrix(analysis),
        ):
            ET.fromstring(svg)  # lanza si está malformado


class TestZeroMatchMarkdown:
    def test_zero_match_table(self, analysis) -> None:
        md = zero_match_markdown(analysis).decode("utf-8")
        for skill_id in ("skill.java", "skill.cpp", "skill.csharp", "skill.git"):
            assert skill_id in md
        assert "matched_records" in md
        assert "0" in md

    def test_zero_match_explanation_and_metadata(self, analysis) -> None:
        md = zero_match_markdown(analysis).decode("utf-8")
        lowered = md.lower()
        assert "not evidence" in lowered
        assert "no_evidence" in lowered
        assert "https://himalayas.app" in md
        assert "technical-skills-0.1.0" in md
        assert "cap_0370798f7af4b0e3" in md
        assert "development_sample" in md
        assert "complete: false" in md
        assert "streamlit" in lowered and "pending" in lowered


class TestNoRawText:
    def test_svg_no_raw_field_keys(self, analysis) -> None:
        svgs = (svg_skill_frequency(analysis), svg_category_coverage(analysis), svg_cooccurrence_matrix(analysis))
        for svg in svgs:
            for raw_key in _RAW_KEYS:
                assert raw_key not in svg

    def test_markdown_no_raw_field_keys(self, analysis) -> None:
        md = zero_match_markdown(analysis)
        for raw_key in _RAW_KEYS:
            assert raw_key not in md

    def test_svg_no_raw_description_text(self, analysis, raw_description_text) -> None:
        raw_bytes = raw_description_text.encode("utf-8")
        for svg in (
            svg_skill_frequency(analysis),
            svg_category_coverage(analysis),
            svg_cooccurrence_matrix(analysis),
        ):
            assert raw_bytes not in svg
            assert b"<p" not in svg

    def test_markdown_no_raw_description_text(self, analysis, raw_description_text) -> None:
        assert raw_description_text.encode("utf-8") not in zero_match_markdown(analysis)

    def test_generated_files_no_raw_text(self, analysis, raw_description_text, tmp_path) -> None:
        out = tmp_path / "viz"
        raw_bytes = raw_description_text.encode("utf-8")
        for path in build_visualizations(analysis, out):
            data = path.read_bytes()
            for raw_key in _RAW_KEYS:
                assert raw_key not in data
            assert raw_bytes not in data


def _build() -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return build_descriptive_analysis(dataset, load_taxonomy(TAXONOMY_PATH))


class TestDeterministicBytes:
    def test_svg_bytes_deterministic(self, analysis, tmp_path) -> None:
        first = tmp_path / "a"
        second = tmp_path / "b"
        first_paths = build_visualizations(analysis, first)
        second_paths = build_visualizations(analysis, second)
        assert [p.name for p in first_paths] == [p.name for p in second_paths]
        for fp, sp in zip(first_paths, second_paths, strict=True):
            assert fp.read_bytes() == sp.read_bytes()

    def test_materialize_deterministic(self, tmp_path) -> None:
        out1 = tmp_path / "one"
        out2 = tmp_path / "two"
        materialize_descriptive_analysis(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            analysis_output_path=out1 / "analysis.json",
            visualizations_dir=out1 / "viz",
        )
        materialize_descriptive_analysis(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            analysis_output_path=out2 / "analysis.json",
            visualizations_dir=out2 / "viz",
        )
        assert (out1 / "analysis.json").read_bytes() == (out2 / "analysis.json").read_bytes()
        for name in EXPECTED_ARTIFACTS:
            assert (out1 / "viz" / name).read_bytes() == (out2 / "viz" / name).read_bytes()


class TestCli:
    def test_cli_writes_analysis_and_visualizations(self, tmp_path) -> None:
        out = tmp_path / "cli"
        code = main(
            [
                "--dataset",
                str(DATASET_PATH),
                "--taxonomy",
                str(TAXONOMY_PATH),
                "--analysis-output",
                str(out / "analysis.json"),
                "--visualizations-dir",
                str(out / "viz"),
            ]
        )
        assert code == 0
        analysis = json.loads((out / "analysis.json").read_text(encoding="utf-8"))
        assert analysis["skill_frequency"]["skill.ai"] == 19
        assert analysis["snapshot_id"] == "cap_0370798f7af4b0e3"
        assert sorted(p.name for p in (out / "viz").iterdir()) == EXPECTED_ARTIFACTS

    def test_cli_repeat_run_is_byte_identical_noop(self, tmp_path) -> None:
        out = tmp_path / "cli"
        args = [
            "--dataset",
            str(DATASET_PATH),
            "--taxonomy",
            str(TAXONOMY_PATH),
            "--analysis-output",
            str(out / "analysis.json"),
            "--visualizations-dir",
            str(out / "viz"),
        ]
        assert main(args) == 0
        first = (out / "analysis.json").read_bytes()
        assert main(args) == 0
        assert (out / "analysis.json").read_bytes() == first

    def test_existing_different_analysis_output_refused(self, tmp_path) -> None:
        out = tmp_path / "analysis.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"stale bytes")
        with pytest.raises(DatasetError, match="different content"):
            materialize_descriptive_analysis(
                dataset_path=DATASET_PATH,
                taxonomy_path=TAXONOMY_PATH,
                analysis_output_path=out,
                visualizations_dir=tmp_path / "viz",
            )
        assert out.read_bytes() == b"stale bytes"

    def test_existing_different_svg_refused(self, tmp_path) -> None:
        out = tmp_path / "analysis.json"
        viz = tmp_path / "viz"
        viz.mkdir(parents=True, exist_ok=True)
        (viz / "skill-frequency.svg").write_bytes(b"stale svg")
        with pytest.raises(DatasetError, match="different content"):
            materialize_descriptive_analysis(
                dataset_path=DATASET_PATH,
                taxonomy_path=TAXONOMY_PATH,
                analysis_output_path=out,
                visualizations_dir=viz,
            )
        assert (viz / "skill-frequency.svg").read_bytes() == b"stale svg"


class TestDefaults:
    def test_default_paths_documented(self) -> None:
        assert DEFAULT_DATASET_PATH == "data/analytics/development-sample-0.1.0.json"
        assert DEFAULT_TAXONOMY_PATH == TAXONOMY_ARTIFACT_DEFAULT_PATH
        assert DEFAULT_ANALYSIS_OUTPUT_PATH == "data/analytics/descriptive-development-sample-0.1.0.json"
        assert DEFAULT_VISUALIZATIONS_DIR == "data/analytics/visualizations/development-sample-0.1.0"


class TestTriangulate:
    """Casos límite del pipeline de artefactos visuales."""

    def test_zero_match_table_contains_no_matched_skills(self, analysis) -> None:
        md = zero_match_markdown(analysis).decode("utf-8")
        for skill_id, count in analysis["skill_frequency"].items():
            if count > 0:
                assert f"| {skill_id} |" not in md

    def test_invalid_dataset_leaves_no_partial_output(self, tmp_path) -> None:
        tampered = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        tampered["sample"]["complete"] = True
        dataset_path = tmp_path / "tampered.json"
        dataset_path.write_text(json.dumps(tampered), encoding="utf-8")
        out = tmp_path / "out"
        with pytest.raises(AnalysisError):
            materialize_descriptive_analysis(
                dataset_path=dataset_path,
                taxonomy_path=TAXONOMY_PATH,
                analysis_output_path=out / "analysis.json",
                visualizations_dir=out / "viz",
            )
        assert not (out / "analysis.json").exists()
        assert not (out / "viz").exists()

    def test_mismatched_taxonomy_version_leaves_no_partial_output(self, tmp_path) -> None:
        doc = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        doc["version"] = "technical-skills-9.9.9"
        taxonomy_path = tmp_path / "taxonomy.json"
        taxonomy_path.write_text(json.dumps(doc), encoding="utf-8")
        out = tmp_path / "out"
        with pytest.raises(AnalysisError):
            materialize_descriptive_analysis(
                dataset_path=DATASET_PATH,
                taxonomy_path=taxonomy_path,
                analysis_output_path=out / "analysis.json",
                visualizations_dir=out / "viz",
            )
        assert not (out / "analysis.json").exists()
        assert not (out / "viz").exists()

    def test_materialized_analysis_json_has_no_raw_text(self, tmp_path, raw_description_text) -> None:
        out = tmp_path / "out"
        materialize_descriptive_analysis(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            analysis_output_path=out / "analysis.json",
            visualizations_dir=out / "viz",
        )
        data = (out / "analysis.json").read_bytes()
        # Los NOMBRES de los campos revisados son metadatos copiados del informe de calidad;
        # los VALORES crudos (texto completo de las descripciones de empleo) no deben aparecer.
        assert raw_description_text.encode("utf-8") not in data

    def test_analysis_json_complete_false_roundtrip(self, tmp_path) -> None:
        out = tmp_path / "out"
        materialize_descriptive_analysis(
            dataset_path=DATASET_PATH,
            taxonomy_path=TAXONOMY_PATH,
            analysis_output_path=out / "analysis.json",
            visualizations_dir=out / "viz",
        )
        parsed = json.loads((out / "analysis.json").read_text(encoding="utf-8"))
        assert parsed["dataset_kind"] == "development_sample"
        assert parsed["sample"]["complete"] is False
        assert parsed["sample"]["records"] == 20
        assert parsed["sample"]["page"] == 1
        assert parsed["snapshot_id"] == "cap_0370798f7af4b0e3"
        assert parsed["taxonomy_version"] == "technical-skills-0.1.0"
