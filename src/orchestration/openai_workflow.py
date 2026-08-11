"""Public workflow facade."""

from .browser_probe import render_browser_evidence
from .codex_runtime import TaskExecutor
from .models import WorkflowRequest, WorkflowResult
from .workflow_base import ApprovalHandler, BrowserRenderer, PublicationWorkflowBase
from .workflow_stages import PublicationStagesMixin


class PublicationWorkflow(PublicationStagesMixin, PublicationWorkflowBase):
    """Five-stage deterministic control plane with bounded Codex execution."""


async def run_publication_workflow(
    request: WorkflowRequest,
    *,
    executor: TaskExecutor | None = None,
    approval_handler: ApprovalHandler | None = None,
    browser_renderer: BrowserRenderer = render_browser_evidence,
) -> WorkflowResult:
    return await PublicationWorkflow(
        executor=executor,
        approval_handler=approval_handler,
        browser_renderer=browser_renderer,
    ).run(request)


OpenAIWorkflow = PublicationWorkflow

__all__ = ["OpenAIWorkflow", "PublicationWorkflow", "run_publication_workflow"]
