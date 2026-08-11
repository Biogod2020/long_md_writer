"""Compatibility entry point for complete HTML publication runs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import WorkflowMode, WorkflowRequest, WorkflowResult
from .openai_workflow import run_publication_workflow


async def run_workflow(
    raw_materials: str,
    reference_docs: Optional[list[str]] = None,
    workspace_base: str = "./workspace",
    job_id: Optional[str] = None,
    debug_mode: bool = False,
    **_: object,
) -> WorkflowResult:
    references = [Path(path) for path in (reference_docs or [])]
    request = WorkflowRequest(
        user_intent=raw_materials,
        reference_files=references,
        output_base=Path(workspace_base),
        job_id=job_id,
        mode=WorkflowMode.HTML,
        auto_approve=True,
        debug=debug_mode,
    )
    return await run_publication_workflow(request)
