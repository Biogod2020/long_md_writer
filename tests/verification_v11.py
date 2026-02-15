"""
Final Verification E2E - v11
Testing SVGAgent Sub-Agent Decoupling & Reflection Loop in Full Workflow.
"""

import asyncio
import os
import shutil
from pathlib import Path
from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.types import AssetSource

async def run_verification_v11():
    print("\n🚀 [VERIFICATION v11] Starting SOTA 2.0 Full Workflow...")
    
    # 1. Load Real Inputs
    prompt_path = Path("inputs/prompt.txt")
    raw_materials_path = Path("inputs/combined_raw_materials.txt")
    
    user_intent = prompt_path.read_text(encoding="utf-8")
    reference_materials = raw_materials_path.read_text(encoding="utf-8")
    
    # 2. Path Configuration
    workspace_base = "workspace"
    job_id = "verification_e2e_v11"
    workspace_path = Path(workspace_base) / job_id
    
    if workspace_path.exists():
        print(f"🧹 Cleaning up existing workspace: {workspace_path}")
        shutil.rmtree(workspace_path)
    
    print(f"📍 Target Workspace: {workspace_path.absolute()}")

    # 3. Execute Workflow
    state = await run_sota2_workflow(
        user_intent=user_intent,
        reference_materials=reference_materials,
        workspace_base=workspace_base,
        job_id=job_id,
        auto_mode=True,
        debug_mode=True
    )
    
    # 4. Report
    print("\n" + "="*50)
    print("📊 VERIFICATION v11 AUDIT REPORT")
    print("="*50)
    
    uar = state.get_uar()
    assets = list(uar.assets.values())
    svg_assets = [a for a in assets if "svg" in a.tags]
    web_assets = [a for a in assets if a.source == AssetSource.WEB]
    
    print(f"Status: {'✅ SUCCESS' if not state.errors else '❌ FAILED'}")
    print(f"SVG Assets (SVGAgent): {len(svg_assets)}")
    print(f"Web Assets (ImageSourcing): {len(web_assets)}")
    
    md_verified = False
    for md_file in (workspace_path / "md").glob("*.md"):
        content = md_file.read_text()
        if "<figure" in content and "data-asset-id" in content:
            md_verified = True
            break

    if not state.errors and len(svg_assets) > 0 and len(web_assets) >= 2 and md_verified:
        print("\n🏆 [VERIFICATION v11] PASSED.")
    else:
        print("\n💀 [VERIFICATION v11] FAILED.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(run_verification_v11())
