"""Public deterministic quality API."""

from pathlib import Path

from .models import QualityReport, StageName, WorkflowMode
from .quality_common import (
    compare_baseline,
    count_words,
    placeholder_count,
    publication_metrics,
    workspace_digest,
)
from .quality_content import assets_report, draft_report, plan_report
from .quality_render import publish_report, qa_report


def quality_report_for_stage(workspace: Path, stage: StageName, mode: WorkflowMode) -> QualityReport:
    workspace = workspace.resolve()
    if stage == StageName.PLAN: return plan_report(workspace, mode)
    if stage == StageName.DRAFT: return draft_report(workspace)
    if stage == StageName.ASSETS: return assets_report(workspace, mode)
    if stage == StageName.PUBLISH: return publish_report(workspace, mode)
    if stage == StageName.QA: return qa_report(workspace, mode)
    raise ValueError(stage)


__all__ = [
    "assets_report", "compare_baseline", "count_words", "draft_report",
    "placeholder_count", "plan_report", "publication_metrics", "publish_report",
    "qa_report", "quality_report_for_stage", "workspace_digest",
]
