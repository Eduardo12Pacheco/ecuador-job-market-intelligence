"""Pruebas del cargador de artefactos de la mesa de evidencia (``job_market_intelligence.demo``).

El cargador de demostración es la capa comprobable detrás de ``app/evidence_desk.py``:
lee los cinco artefactos versionados bajo ``data/`` y los normaliza para su
visualización, con respaldos por campo para que un campo opcional faltante nunca
rompa la aplicación. Estas pruebas verifican los conteos locales reales que la
interfaz debe mostrar, la derivación de estado final-para-la-muestra y el
contrato de degradación elegante.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from job_market_intelligence.demo import artifacts as A
from job_market_intelligence.demo.artifacts import (
    DemoDataError,
    JobRecord,
    format_metric,
    load_demo_bundle,
    prettify_slug,
    verify_quote,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle() -> A.DemoBundle:
    return load_demo_bundle(REPO_ROOT)


class TestRealArtifacts:
    """Las secciones de la franja de evidencia y de auditoría deben mostrar exactamente estos conteos locales."""

    def test_bundle_loads_all_artifacts(self, bundle: A.DemoBundle) -> None:
        assert bundle.dataset.record_count == 20
        assert len(bundle.taxonomy.skills) == 37
        assert len(bundle.taxonomy.categories) == 8
        assert len(bundle.review.labels) == 740
        assert bundle.dataset.sample.get("complete") is False
        assert bundle.review.annotation_status == "human_review_complete"
        assert bundle.review.human_review_required is False
        assert bundle.review.human_review_complete is True
        assert bundle.dataset.dataset_version == "0.1.0"
        assert bundle.dataset.matcher_version == "keyword-baseline-0.1.0"
        assert bundle.taxonomy.version == "technical-skills-0.1.0"
        assert bundle.review.evaluation_version == "skill-extraction-review-0.3.0"

    def test_cross_artifact_metadata_is_consistent(self, bundle: A.DemoBundle) -> None:
        # La mesa solo muestra el estado fijado de la muestra de desarrollo: el
        # conjunto de datos, la revisión y el informe deben coincidir en instantánea y versiones.
        assert bundle.dataset.dataset_kind == "development_sample"
        assert bundle.dataset.taxonomy_version == "technical-skills-0.1.0"
        assert bundle.dataset.capture_identity.get("snapshot_id") == "cap_0370798f7af4b0e3"
        assert bundle.review.snapshot_id == "cap_0370798f7af4b0e3"
        assert bundle.review.taxonomy_version == "technical-skills-0.1.0"
        assert bundle.review.dataset_type == "development_sample"
        assert bundle.report.snapshot_id == "cap_0370798f7af4b0e3"
        assert bundle.report.taxonomy_version == "technical-skills-0.1.0"

    def test_all_five_artifact_files_load(self, bundle: A.DemoBundle) -> None:
        assert A.DATASET_PATH.is_file()
        assert A.DESCRIPTIVE_PATH.is_file()
        assert A.REVIEW_PATH.is_file()
        assert A.REPORT_PATH.is_file()
        assert A.TAXONOMY_PATH.is_file()
        assert A.load_dataset(A.DATASET_PATH).record_count == 20
        assert "skill_frequency" in A.load_descriptive(A.DESCRIPTIVE_PATH)
        assert len(A.load_review(A.REVIEW_PATH).labels) == 740
        assert A.load_report(A.REPORT_PATH).primary_metrics.get("tp") == 40
        assert len(A.load_taxonomy_info(A.TAXONOMY_PATH).skills) == 37
    def test_review_label_distribution(self, bundle: A.DemoBundle) -> None:
        assert bundle.review.label_counts() == {
            "supported": 40,
            "not_supported": 700,
            "uncertain": 0,
        }

    def test_report_metrics_and_final_for_sample_flag(self, bundle: A.DemoBundle) -> None:
        assert bundle.report.is_provisional is False
        assert bundle.report.human_review_complete is True
        m = bundle.report.primary_metrics
        assert m["tp"] == 40
        assert m["fp"] == 16
        assert m["fn"] == 0
        assert m["tn"] == 684
        assert format_metric(m["precision"]) == "0.7143"
        assert format_metric(m["recall"]) == "1.0000"
        assert format_metric(m["f1"]) == "0.8333"
        assert len(bundle.report.false_positives) == 16
        assert len(bundle.report.false_negatives) == 0
        assert len(bundle.report.human_queue) == 0
        assert len(bundle.report.human_review_decisions) == 7

    def test_every_label_joins_a_record_and_a_taxonomy_skill(self, bundle: A.DemoBundle) -> None:
        for label in bundle.review.labels:
            assert bundle.dataset.record_by_source(label.source_id) is not None
            assert bundle.taxonomy.skill_by_id(label.skill_id) is not None

    def test_every_supported_evidence_quote_verifies_against_the_record(
        self, bundle: A.DemoBundle
    ) -> None:
        checked = 0
        for label in bundle.review.labels:
            record = bundle.dataset.record_by_source(label.source_id)
            for ev in label.evidence:
                value = record.field_value(ev.field)
                assert verify_quote(value, ev.char_start, ev.char_end, ev.exact_quote) is True
                checked += 1
        assert checked > 0

    def test_category_labels_cover_the_taxonomy_categories(self, bundle: A.DemoBundle) -> None:
        assert set(bundle.taxonomy.category_labels) >= set(bundle.taxonomy.categories)

    def test_landscape_counts(self, bundle: A.DemoBundle) -> None:
        freq = A.skill_frequency(bundle.descriptive)
        zero = A.zero_match_skills(bundle.descriptive)
        assert len(freq) == 33  # skills with at least one matched record
        assert len(zero) == 4  # taxonomy skills with zero matched records
        assert len(freq) + len(zero) == len(bundle.taxonomy.skills)
        cats = A.category_coverage(bundle.descriptive)
        assert len(cats) == 8


class TestFallbacks:
    """Los campos opcionales faltantes deben degradarse con elegancia, nunca romper la aplicación."""

    def test_minimal_record_gets_display_fallbacks(self) -> None:
        record = JobRecord.from_dict({"source_id": "s1"})
        assert record.display_title == "Untitled role"
        assert record.display_company == "Unknown company"
        assert record.display_location == "Not stated"
        assert record.excerpt == ""
        assert record.salary == "Not disclosed"
        assert record.skills == ()
        assert record.evidence == ()

    def test_placeholder_company_raw_uses_the_slug(self) -> None:
        record = JobRecord.from_dict(
            {"source_id": "s1", "company_raw": "name", "company_slug_raw": "micro1"}
        )
        assert record.display_company == "Micro1"

    def test_prettify_slug(self) -> None:
        assert prettify_slug("micro1") == "Micro1"
        assert prettify_slug("bjak") == "Bjak"
        assert prettify_slug("clera") == "Clera"
        assert prettify_slug("") == "Unknown company"

    def test_metric_formatting(self) -> None:
        assert format_metric(0.7450980392156863) == "0.7451"
        assert format_metric(1.0) == "1.0000"
        assert format_metric(0.8539325842696629) == "0.8539"
        assert format_metric(None) == "n/a"

    def test_verify_quote_contract(self) -> None:
        assert verify_quote("abcdef", 0, 3, "abc") is True
        assert verify_quote("abcdef", 0, 3, "abx") is False
        assert verify_quote("abcdef", 0, 99, "abc") is False
        assert verify_quote("abcdef", 2, 2, "abc") is False

    def test_missing_artifact_file_raises_demo_error(self) -> None:
        missing = REPO_ROOT / "data" / "analytics" / "does-not-exist-0.0.0.json"
        with pytest.raises(DemoDataError):
            load_demo_bundle(REPO_ROOT, paths={"dataset": missing})

    def test_missing_evidence_excerpt_falls_back_to_empty(self) -> None:
        record = JobRecord.from_dict(
            {
                "source_id": "s1",
                "skill_evidence": {
                    "skills": ["skill.ai"],
                    "evidence": [{"skill_id": "skill.ai", "field": "title_raw"}],
                },
            }
        )
        entry = record.evidence[0]
        assert entry.excerpt == ""
        assert entry.matched_term == ""

    def test_non_list_skills_and_evidence_do_not_crash(self) -> None:
        record = JobRecord.from_dict(
            {"source_id": "s1", "skill_evidence": {"skills": None, "evidence": None}}
        )
        assert record.skills == ()
        assert record.evidence == ()

    def test_salary_formatting(self) -> None:
        record = JobRecord.from_dict(
            {
                "source_id": "s1",
                "salary_min_raw": 60000,
                "salary_max_raw": 90000,
                "salary_period_raw": "annual",
                "currency_raw": "USD",
            }
        )
        assert record.salary == "USD 60,000 - USD 90,000 per annual"

    def test_graceful_salary_with_only_max(self) -> None:
        record = JobRecord.from_dict(
            {"source_id": "s1", "salary_max_raw": 50000, "currency_raw": "USD"}
        )
        assert record.salary == "up to USD 50,000"


class TestHumanReviewContract:
    def test_human_queue_is_closed_after_approval(self, bundle: A.DemoBundle) -> None:
        assert bundle.report.human_queue == ()
        assert len(bundle.report.human_review_decisions) == 7
        assert all(item.get("final_label") in {"supported", "not_supported", "uncertain"}
                   for item in bundle.report.human_review_decisions)

    def test_no_uncertain_final_labels_remain(self, bundle: A.DemoBundle) -> None:
        assert [label for label in bundle.review.labels if label.label == "uncertain"] == []

    def test_all_false_positives_are_keyword_skill_matches(self, bundle: A.DemoBundle) -> None:
        assert {fp.get("skill_id") for fp in bundle.report.false_positives} == {
            "skill.ai",
            "skill.data_science",
            "skill.machine_learning",
        }


class TestStatusLabels:
    """La aplicación expone el estado final-para-la-muestra sin exagerar el alcance del mercado."""

    def test_status_labels_are_final_for_sample(self, bundle: A.DemoBundle) -> None:
        assert bundle.status.labels == (
            "demo-ready",
            "evaluation-final",
            "human-reviewed",
        )
        assert bundle.status.demo_ready is True
        assert bundle.status.evaluation_final is True
        assert bundle.status.human_reviewed is True

    def test_derived_status_is_demo_ready_after_final_gate(self, bundle: A.DemoBundle) -> None:
        assert bundle.status.labels[0] == "demo-ready"
        assert bundle.status.labels[1] == "evaluation-final"
        assert bundle.status.labels[2] == "human-reviewed"


class TestPinnedStateValidation:
    """El cargador debe fallar claramente cuando el estado central es inconsistente.

    Los campos opcionales de los registros siguen degradándose a valores
    placeholder (ver TestFallbacks), pero los conteos y metadatos fijados —
    20 registros, 37 habilidades, 740 etiquetas, instantánea, versión de
    taxonomía, muestra de desarrollo, complete: false, cola cerrada y
    métricas exactas final-para-la-muestra — son un contrato estricto.
    """

    @staticmethod
    def _with_dataset(bundle: A.DemoBundle, **changes) -> A.DemoBundle:
        return dataclasses.replace(
            bundle, dataset=dataclasses.replace(bundle.dataset, **changes)
        )

    @staticmethod
    def _with_review(bundle: A.DemoBundle, **changes) -> A.DemoBundle:
        return dataclasses.replace(
            bundle, review=dataclasses.replace(bundle.review, **changes)
        )

    @staticmethod
    def _with_report(bundle: A.DemoBundle, **changes) -> A.DemoBundle:
        return dataclasses.replace(
            bundle, report=dataclasses.replace(bundle.report, **changes)
        )

    @staticmethod
    def _with_taxonomy(bundle: A.DemoBundle, **changes) -> A.DemoBundle:
        return dataclasses.replace(
            bundle, taxonomy=dataclasses.replace(bundle.taxonomy, **changes)
        )

    def test_real_bundle_validates(self, bundle: A.DemoBundle) -> None:
        A.validate_bundle(bundle)

    def test_rejects_wrong_record_count(self, bundle: A.DemoBundle) -> None:
        bad = self._with_dataset(bundle, records=bundle.dataset.records[:19])
        with pytest.raises(A.DemoDataError, match="record count"):
            A.validate_bundle(bad)

    def test_rejects_wrong_taxonomy_skill_count(self, bundle: A.DemoBundle) -> None:
        bad = self._with_taxonomy(bundle, skills=bundle.taxonomy.skills[:36])
        with pytest.raises(A.DemoDataError, match="taxonomy"):
            A.validate_bundle(bad)

    def test_rejects_wrong_snapshot(self, bundle: A.DemoBundle) -> None:
        identity = dict(bundle.dataset.capture_identity, snapshot_id="cap_0000000000000000")
        bad = self._with_dataset(bundle, capture_identity=identity)
        with pytest.raises(A.DemoDataError, match="snapshot"):
            A.validate_bundle(bad)

    def test_rejects_taxonomy_version_mismatch(self, bundle: A.DemoBundle) -> None:
        bad = self._with_taxonomy(bundle, version="technical-skills-9.9.9")
        with pytest.raises(A.DemoDataError, match="technical-skills"):
            A.validate_bundle(bad)

    def test_rejects_non_development_sample_kind(self, bundle: A.DemoBundle) -> None:
        bad = self._with_dataset(bundle, dataset_kind="full_feed")
        with pytest.raises(A.DemoDataError, match="development_sample"):
            A.validate_bundle(bad)

    def test_rejects_complete_true_sample(self, bundle: A.DemoBundle) -> None:
        sample = dict(bundle.dataset.sample, complete=True)
        bad = self._with_dataset(bundle, sample=sample)
        with pytest.raises(A.DemoDataError, match="complete"):
            A.validate_bundle(bad)

    def test_rejects_wrong_label_count(self, bundle: A.DemoBundle) -> None:
        bad = self._with_review(bundle, labels=bundle.review.labels[:739])
        with pytest.raises(A.DemoDataError, match="740"):
            A.validate_bundle(bad)

    def test_rejects_nonempty_human_queue(self, bundle: A.DemoBundle) -> None:
        bad = self._with_report(bundle, human_queue=({"source_id": "unexpected"},))
        with pytest.raises(A.DemoDataError, match="0"):
            A.validate_bundle(bad)

    def test_rejects_metric_drift(self, bundle: A.DemoBundle) -> None:
        metrics = dict(bundle.report.metrics, primary={"tp": 99, "fp": 13, "fn": 0, "tn": 684})
        bad = self._with_report(bundle, metrics=metrics)
        with pytest.raises(A.DemoDataError, match="metric"):
            A.validate_bundle(bad)

    def test_rejects_unknown_label_value(self, bundle: A.DemoBundle) -> None:
        label = dataclasses.replace(bundle.review.labels[0], label="bogus", final_label="bogus")
        bad = self._with_review(bundle, labels=(label,) + bundle.review.labels[1:])
        with pytest.raises(A.DemoDataError, match="label"):
            A.validate_bundle(bad)

    def test_rejects_incompatible_status_claim_in_review(self, bundle: A.DemoBundle) -> None:
        bad = self._with_review(bundle, annotation_status="gold")
        with pytest.raises(A.DemoDataError, match="incompatible"):
            A.validate_bundle(bad)

    def test_rejects_incompatible_status_claim_in_report(self, bundle: A.DemoBundle) -> None:
        bad = self._with_report(bundle, annotation_status="human_reviewed")
        with pytest.raises(A.DemoDataError, match="incompatible"):
            A.validate_bundle(bad)

    def test_rejects_cross_artifact_taxonomy_version_mismatch(self, bundle: A.DemoBundle) -> None:
        bad = self._with_review(bundle, taxonomy_version="technical-skills-9.9.9")
        with pytest.raises(A.DemoDataError, match="taxonomy_version"):
            A.validate_bundle(bad)

    def test_rejects_incomplete_human_review(self, bundle: A.DemoBundle) -> None:
        bad = self._with_review(bundle, human_review_complete=False)
        with pytest.raises(A.DemoDataError, match="human_review_complete"):
            A.validate_bundle(bad)

    def test_rejects_report_without_metrics(self, bundle: A.DemoBundle) -> None:
        bad = self._with_report(bundle, metrics={})
        with pytest.raises(A.DemoDataError, match="metric"):
            A.validate_bundle(bad)

    def test_rejects_malformed_records_shape(self, bundle: A.DemoBundle) -> None:
        # Un conjunto de datos cuyos registros no son una lista se normaliza a cero
        # registros y luego falla el conteo fijado con un mensaje claro.
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.json"
            path.write_text(json.dumps({"records": "not-a-list"}), encoding="utf-8")
            dataset = A.load_dataset(path)
        bad = dataclasses.replace(bundle, dataset=dataset)
        with pytest.raises(A.DemoDataError, match="record count"):
            A.validate_bundle(bad)

    def test_derive_status_does_not_claim_final_for_incomplete_report(self, bundle: A.DemoBundle) -> None:
        report = dataclasses.replace(
            bundle.report,
            annotation_status="draft_evaluation",
            human_review_required=True,
            human_review_complete=False,
        )
        status = A.derive_status(report)
        assert status.evaluation_final is False
        assert status.human_reviewed is False


class TestLabelHandling:
    """Las etiquetas de enumerado cerrado se manejan explícitamente; los valores desconocidos degradan."""

    def test_closed_enum_label_counts(self, bundle: A.DemoBundle) -> None:
        counts = bundle.review.label_counts()
        assert set(counts) == {"supported", "not_supported", "uncertain"}
        assert counts["supported"] + counts["not_supported"] + counts["uncertain"] == 740

    def test_unknown_label_value_degrades_gracefully_in_tolerant_loader(self) -> None:
        import json
        from pathlib import Path

        import tempfile

        doc = json.loads(A.REVIEW_PATH.read_text(encoding="utf-8"))
        doc["labels"][0]["label"] = "bogus"
        doc["labels"][0]["final_label"] = "bogus"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            review = A.load_review(path)
        assert review.labels[0].label == "bogus"
        assert review.labels[0].is_uncertain is False

    def test_every_evidence_quote_verifies_against_the_record(
        self, bundle: A.DemoBundle
    ) -> None:
        checked = 0
        for label in bundle.review.labels:
            record = bundle.dataset.record_by_source(label.source_id)
            for ev in label.evidence:
                value = record.field_value(ev.field)
                assert verify_quote(value, ev.char_start, ev.char_end, ev.exact_quote) is True
                checked += 1
        assert checked == 43  # evidencia conservada: 38 positivos históricos + 5 pares inciertos históricos


class TestNetworkBoundary:
    """El cargador de demostración y la ruta de la aplicación nunca deben importar ni llamar a la red.

    Guardia a nivel de fuente (AST): el paquete de demostración usa solo la
    biblioteca estándar y la aplicación solo importa Streamlit; nada puede
    traer httpx/requests/urllib/socket ni invocar llamadas estilo urlopen.
    """

    @staticmethod
    def _banned_imports(path: Path) -> list[str]:
        import ast

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        banned: set[str] = {"httpx", "requests", "urllib", "socket", "aiohttp", "http"}
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in banned:
                        found.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in banned:
                    found.add(node.module)
        return sorted(found)

    @staticmethod
    def _network_call_hints(path: Path) -> list[str]:
        source = path.read_text(encoding="utf-8")
        hints = [
            token
            for token in ("urlopen", "requests.", "httpx.", "urllib.", "socket.", "aiohttp")
            if token in source
        ]
        return hints

    def test_demo_loader_imports_no_network_modules(self) -> None:
        path = REPO_ROOT / "src" / "job_market_intelligence" / "demo" / "artifacts.py"
        assert self._banned_imports(path) == []

    def test_demo_loader_source_has_no_network_call_hints(self) -> None:
        path = REPO_ROOT / "src" / "job_market_intelligence" / "demo" / "artifacts.py"
        assert self._network_call_hints(path) == []

    def test_app_imports_no_network_modules(self) -> None:
        path = REPO_ROOT / "app" / "evidence_desk.py"
        assert self._banned_imports(path) == []

    def test_app_source_has_no_network_call_hints(self) -> None:
        path = REPO_ROOT / "app" / "evidence_desk.py"
        assert self._network_call_hints(path) == []


class TestSpanishDisplayHelpers:
    """Helpers de presentación en español para la superficie pública.

    La interfaz pública es profesional en español: las métricas usan coma
    decimal, los veredictos usan palabras humanas y los campos revisados
    tienen nombres legibles. El enumerado técnico y los nombres crudos
    quedan solo para «Detalles técnicos».
    """

    def test_format_metric_es_usa_coma_decimal(self) -> None:
        assert A.format_metric_es(0.7450980392156863) == "0,7451"
        assert A.format_metric_es(1.0) == "1,0"
        assert A.format_metric_es(0.8539325842696629) == "0,8539"
        assert A.format_metric_es(0.9753787878787878) == "0,9754"
        assert A.format_metric_es(0.5) == "0,5"
        assert A.format_metric_es(None) == "n/d"

    def test_verdict_es_traduce_el_enumerado(self) -> None:
        assert A.verdict_es("supported") == "respaldado"
        assert A.verdict_es("not_supported") == "no respaldado"
        assert A.verdict_es("uncertain") == "incierto"
        # Valor desconocido: degrada sin romper.
        assert A.verdict_es("bogus") == "bogus"

    def test_field_es_nombres_legibles_de_campos(self) -> None:
        assert A.field_es("title_raw") == "Título"
        assert A.field_es("excerpt_raw") == "Extracto"
        assert A.field_es("categories_raw") == "Categorías"
        assert A.field_es("description_html_raw") == "Descripción"
        assert A.field_es("unknown_field") == "Campo de la oferta"


class TestSkillLandscapeHelpers:
    def test_frequency_sorted_descending(self, bundle: A.DemoBundle) -> None:
        freq = A.skill_frequency(bundle.descriptive)
        values = list(freq.values())
        assert values == sorted(values, reverse=True)

    def test_empty_descriptive_degrades_to_empty_helpers(self) -> None:
        assert A.skill_frequency({}) == {}
        assert A.category_coverage({}) == []
        assert A.zero_match_skills({}) == []

    def test_missing_report_file_raises_demo_error(self) -> None:
        missing = REPO_ROOT / "data" / "evaluation" / "missing-report.json"
        with pytest.raises(DemoDataError):
            A.load_report(missing)

    def test_report_without_metrics_has_empty_primary(self, bundle: A.DemoBundle) -> None:
        report = A.ReviewReport(
            annotation_status="draft_second_pass",
            human_review_required=True,
            label_distribution={},
            metrics={},
            false_positives=(),
            false_negatives=(),
            human_queue=(),
            first_vs_second={},
            uncertainty={},
            coverage={},
            definitions={},
            limitations=(),
            guardrails=(),
            warnings=(),
            sample={},
        )
        assert report.is_provisional is True
        assert report.primary_metrics == {}

    def test_category_coverage_shape(self, bundle: A.DemoBundle) -> None:
        cats = A.category_coverage(bundle.descriptive)
        first = cats[0]
        assert {"category", "records", "matched_skill_count"} <= set(first)
