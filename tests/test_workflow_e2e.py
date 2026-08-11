from __future__ import annotations

from pathlib import Path
import hashlib
import json

import pytest
from PIL import Image

from src.orchestration.codex_runtime import FakeExecutor
from src.orchestration.models import CodexTaskResult, StageName, WorkflowMode, WorkflowRequest
from src.orchestration.openai_workflow import run_publication_workflow
from src.orchestration.state_store import StateStore


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _completed(summary: str = "done") -> CodexTaskResult:
    return CodexTaskResult(status="completed", summary=summary)


def _plan_payload() -> dict:
    return {
        "schema_version": 2,
        "project_title": "Reliable Agent Systems",
        "audience": "Agent developers",
        "language": "en",
        "objectives": ["Explain reliable orchestration", "Explain deterministic verification"],
        "sections": [
            {
                "id": "orchestration",
                "title": "Reliable Orchestration",
                "objective": "Explain bounded orchestration",
                "estimated_words": 300,
                "required_evidence": ["provided request"],
                "visual_opportunities": [],
            },
            {
                "id": "verification",
                "title": "Deterministic Verification",
                "objective": "Explain independent verification",
                "estimated_words": 300,
                "required_evidence": ["provided request"],
                "visual_opportunities": [],
            },
        ],
        "quality_contract": {
            "minimum_section_coverage": 1.0,
            "minimum_word_ratio": 0.8,
            "require_zero_broken_assets": True,
            "require_zero_unresolved_visual_directives": True,
            "require_zero_placeholders": True,
            "minimum_quality_score": 85.0,
        },
    }


async def _handler(task):
    ws = task.workspace
    if task.stage == StageName.PLAN:
        (ws / "project_brief.md").write_text("# Brief\n\n" + ("rigorous scope " * 30))
        (ws / "plan.json").write_text(json.dumps(_plan_payload(), indent=2))
    elif task.stage == StageName.DRAFT:
        relative = task.allowed_paths[0]
        section_id = Path(relative).stem
        title = "Reliable Orchestration" if section_id == "orchestration" else "Deterministic Verification"
        target = ws / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"## {title}\n\n" + ("evidence grounded explanation " * 130))
    elif task.stage == StageName.ASSETS:
        (ws / "md").mkdir(parents=True, exist_ok=True)
        for source in (ws / "drafts").glob("*.md"):
            (ws / "md" / source.name).write_text(source.read_text())
        (ws / "assets").mkdir(parents=True, exist_ok=True)
        (ws / "assets" / "asset-manifest.json").write_text(
            json.dumps({"schema_version": 2, "assets": []})
        )
    elif task.stage == StageName.PUBLISH:
        plan = _plan_payload()
        markdown = "# Reliable Agent Systems\n\n" + "\n\n".join(
            (ws / "md" / f"{section['id']}.md").read_text() for section in plan["sections"]
        )
        (ws / "final.md").write_text(markdown)
        if "final.html" in task.allowed_paths:
            text = " ".join(markdown.replace("#", "").split())
            (ws / "final.html").write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Reliable Agent Systems</title>"
                "<style>body{max-width:70ch;margin:auto}main{padding:2rem}</style></head>"
                f"<body><main><article><h1>Reliable Agent Systems</h1><p>{text}</p></article></main></body></html>"
            )
    elif "qa-audit" in task.task_id:
        path = ws / "qa" / "audit-findings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "schema_version": 2,
            "review_role": "independent_auditor",
            "artifact_hashes": {},
            "dimension_scores": {},
            "critical_issues": [],
            "repair_instructions": [],
            "unsupported_claims": [],
        }))
    elif "qa-verify" in task.task_id:
        dimensions = {
            name: {"score": 95, "findings": []}
            for name in ["accuracy", "completeness", "coherence", "visual_quality", "rendering", "citation_hygiene"]
        }
        payload = {
            "schema_version": 2,
            "review_role": "independent_verifier",
            "status": "pass",
            "summary": "verified",
            "audit_findings_sha256": _sha(ws / "qa" / "audit-findings.json"),
            "final_md_sha256": _sha(ws / "final.md"),
            "final_html_sha256": _sha(ws / "final.html") if (ws / "final.html").is_file() else "",
            "browser_report_sha256": _sha(ws / "qa" / "browser_report.json") if (ws / "qa" / "browser_report.json").is_file() else "",
            "dimensions": dimensions,
            "critical_issues": [],
            "repairs_verified": [],
            "commands_run": [],
        }
        (ws / "qa_report.json").write_text(json.dumps(payload))
    else:
        raise AssertionError(f"unexpected task: {task.task_id}")
    return _completed()


async def _browser(workspace: Path):
    qa = workspace / "qa"
    qa.mkdir(exist_ok=True)
    desktop = qa / "render-desktop.png"
    mobile = qa / "render-mobile.png"
    Image.new("RGB", (40, 40), "white").save(desktop)
    Image.new("RGB", (40, 40), "white").save(mobile)
    report = {
        "schema_version": 2,
        "producer": "python-control-plane",
        "control_plane_generated": True,
        "status": "pass",
        "final_html_sha256": _sha(workspace / "final.html"),
        "desktop_sha256": _sha(desktop),
        "mobile_sha256": _sha(mobile),
        "views": {
            "desktop": {"viewportWidth": 1440, "viewportHeight": 1000, "documentWidth": 1440, "documentHeight": 1200, "textLength": 1000, "imageCount": 0, "brokenImages": 0, "horizontalOverflow": False},
            "mobile": {"viewportWidth": 390, "viewportHeight": 844, "documentWidth": 390, "documentHeight": 1200, "textLength": 1000, "imageCount": 0, "brokenImages": 0, "horizontalOverflow": False},
        },
        "console_errors": [], "page_errors": [], "request_failures": [], "error": None,
    }
    StateStore.atomic_write_json(qa / "browser_report.json", report)
    return report


@pytest.mark.asyncio
async def test_complete_html_workflow_and_resume(tmp_path: Path) -> None:
    executor = FakeExecutor(_handler)
    request = WorkflowRequest(
        user_intent="Create a rigorous publication about reliable agents.",
        output_base=tmp_path,
        job_id="e2e",
        mode=WorkflowMode.HTML,
        auto_approve=True,
        debug=True,
    )
    first = await run_publication_workflow(request, executor=executor, browser_renderer=_browser)
    assert first.succeeded, first.errors
    assert Path(first.final_html_path).is_file()
    task_count = len(executor.tasks)

    second = await run_publication_workflow(request, executor=executor, browser_renderer=_browser)
    assert second.succeeded, second.errors
    assert len(executor.tasks) == task_count


@pytest.mark.asyncio
async def test_input_change_invalidates_completed_job(tmp_path: Path) -> None:
    executor = FakeExecutor(_handler)
    base = dict(output_base=tmp_path, job_id="change", mode=WorkflowMode.HTML, auto_approve=True, debug=True)
    first = await run_publication_workflow(WorkflowRequest(user_intent="Version one", **base), executor=executor, browser_renderer=_browser)
    assert first.succeeded
    count = len(executor.tasks)
    second = await run_publication_workflow(WorkflowRequest(user_intent="Version two", **base), executor=executor, browser_renderer=_browser)
    assert second.succeeded
    assert len(executor.tasks) > count
