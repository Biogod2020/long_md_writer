from pathlib import Path

import json

from src.orchestration.models import WorkflowMode
from src.orchestration.quality import compare_baseline, publication_metrics, publish_report


def _plan() -> dict:
    return {
        "schema_version": 2,
        "project_title": "Guide",
        "audience": "Experts",
        "language": "en",
        "objectives": ["Explain"],
        "sections": [
            {
                "id": "section-one",
                "title": "Section One",
                "objective": "Explain",
                "estimated_words": 500,
                "required_evidence": ["provided material"],
                "visual_opportunities": [],
            }
        ],
        "quality_contract": {},
    }


def test_publication_metrics_does_not_double_count_final_and_sections(tmp_path: Path) -> None:
    (tmp_path / "md").mkdir()
    (tmp_path / "md" / "section.md").write_text("word " * 100)
    (tmp_path / "final.md").write_text("word " * 100)
    assert publication_metrics(tmp_path)["word_count"] == 100


def test_publish_rejects_active_html(tmp_path: Path) -> None:
    (tmp_path / "plan.json").write_text(json.dumps(_plan()))
    body = "# Guide\n\n## Section One\n\n" + ("word " * 600)
    (tmp_path / "final.md").write_text(body)
    (tmp_path / "final.html").write_text(
        "<html><head><title>Guide</title></head><body><main><h1>Guide</h1>"
        + ("safe text " * 100)
        + '<script src="https://example.com/x.js"></script></main></body></html>'
    )
    report = publish_report(tmp_path, WorkflowMode.HTML)
    assert not report.passed
    assert any(check.code == "publish.html_no_remote_resources" and not check.passed for check in report.checks)


def test_baseline_detects_material_content_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir(); candidate.mkdir()
    (baseline / "final.md").write_text("word " * 1000)
    (candidate / "final.md").write_text("word " * 600)
    comparison = compare_baseline(candidate, baseline)
    assert not comparison.passed
    assert any("content volume" in item for item in comparison.regressions)
