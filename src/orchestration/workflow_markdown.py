"""Compatibility entry point for Markdown-only publication runs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import WorkflowMode, WorkflowRequest, WorkflowResult
from .openai_workflow import run_publication_workflow


async def run_sota2_workflow(
    user_intent: str,
    reference_materials: str = "",
    assets_input_dir: str = "inputs",
    workspace_base: str = "./workspace",
    job_id: Optional[str] = None,
    skip_vision: bool = False,
    skip_asset_audit: bool = False,
    debug_mode: bool = False,
    mounted_workspaces: Optional[dict[str, str]] = None,
    auto_mode: bool = False,
    **_: object,
) -> WorkflowResult:
    del skip_vision, skip_asset_audit, mounted_workspaces
    assets = Path(assets_input_dir)
    request = WorkflowRequest(
        user_intent=user_intent,
        inline_reference_materials=reference_materials,
        assets_dir=assets if assets.is_dir() else None,
        output_base=Path(workspace_base),
        job_id=job_id,
        mode=WorkflowMode.MARKDOWN,
        auto_approve=auto_mode,
        debug=debug_mode,
    )
    return await run_publication_workflow(request)
