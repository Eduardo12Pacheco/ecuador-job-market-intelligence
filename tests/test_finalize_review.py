"""Pruebas offline del materializador de revisión humana v0.3.0."""

from __future__ import annotations

import json
from pathlib import Path

from job_market_intelligence.analysis.finalize_review import (
    HUMAN_DECISIONS,
    materialize_final_review,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_V020 = REPO_ROOT / "data/evaluation/skill-extraction-review-0.2.0.json"
REPORT_V020 = REPO_ROOT / "data/evaluation/skill-extraction-review-report-0.2.0.json"
DATASET = REPO_ROOT / "data/analytics/development-sample-0.1.0.json"
FINAL = REPO_ROOT / "data/evaluation/skill-extraction-review-0.3.0.json"
FINAL_REPORT = REPO_ROOT / "data/evaluation/skill-extraction-review-report-0.3.0.json"


def test_materializer_reproduces_committed_final_artifacts(tmp_path: Path) -> None:
    before_review = REVIEW_V020.read_bytes()
    before_report = REPORT_V020.read_bytes()
    output, output_report = materialize_final_review(
        review_path=REVIEW_V020,
        report_path=REPORT_V020,
        dataset_path=DATASET,
        artifact_output_path=tmp_path / "review.json",
        report_output_path=tmp_path / "report.json",
    )

    assert output.read_bytes() == FINAL.read_bytes()
    assert output_report.read_bytes() == FINAL_REPORT.read_bytes()
    assert REVIEW_V020.read_bytes() == before_review
    assert REPORT_V020.read_bytes() == before_report


def test_final_artifacts_close_queue_and_record_all_approvals() -> None:
    review = json.loads(FINAL.read_text(encoding="utf-8"))
    report = json.loads(FINAL_REPORT.read_text(encoding="utf-8"))

    assert review["annotation_status"] == "human_review_complete"
    assert review["human_review_required"] is False
    assert review["human_review_complete"] is True
    assert len(review["labels"]) == 740
    assert {item["adjudication_id"] for item in review["labels"] if "adjudication_id" in item} == {
        decision["item_id"] for decision in HUMAN_DECISIONS
    }
    assert report["human_review_queue"] == {
        "count": 0,
        "items": [],
        "note": (
            "current state: queue closed; the seven approved decisions are recorded in "
            "human_review_decisions and the frozen v0.2.0 queue is preserved under "
            "historical.human_review_queue"
        ),
    }
    assert len(report["human_review_decisions"]) == 7
    assert report["label_distribution"]["final"] == {
        "supported": 40,
        "not_supported": 700,
        "uncertain": 0,
        "total": 740,
    }
    primary = report["metrics"]["primary"]
    assert primary["tp"] == 40
    assert primary["fp"] == 16
    assert primary["fn"] == 0
    assert primary["tn"] == 684
    assert primary["precision"] == 40 / 56
    assert primary["recall"] == 1.0
    assert primary["f1"] == 0.8333333333333333
    assert primary["denominators"] == {"tp_fn": 40, "tp_fp": 56}
    assert report["historical"]["human_review_queue"]["count"] == 7
