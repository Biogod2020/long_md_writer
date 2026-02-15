"""
E2E Test for SVG Sub-Agent Integration in SOTA 2.0 Workflow
"""

import asyncio
import os
from pathlib import Path
from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.types import AssetSource

async def test_e2e_svg_subagent():
    print("
🚀 [E2E TEST] Starting SOTA 2.0 Workflow with SVG Sub-Agent...")
    
    # Define a prompt that forces the creation of a technical SVG diagram
    user_intent = """
    Create a technical document explaining the 'Hall Effect'. 
    Include a detailed SVG diagram showing a conductor with current, 
    an external magnetic field, and the resulting accumulation of charges (Hall voltage).
    The diagram must have clear labels for 'Current (I)', 'Magnetic Field (B)', and 'Hall Voltage (Vh)'.
    """
    
    job_id = "e2e_svg_subagent_test"
    workspace_base = "data/test_artifacts/e2e_svg"
    
    # Run the full workflow in auto_mode to bypass HITL interruptions
    state = await run_sota2_workflow(
        user_intent=user_intent,
        workspace_base=workspace_base,
        job_id=job_id,
        auto_mode=True, # Auto-approve brief, outline, and assets
        debug_mode=True
    )
    
    workspace_path = Path(workspace_base) / job_id
    
    print("
--- [E2E RESULTS] ---")
    print(f"Job ID: {state.job_id}")
    print(f"Status: {'SUCCESS' if not state.errors else 'FAILED'}")
    
    if state.errors:
        print("Errors encountered:")
        for err in state.errors:
            print(f"  - {err}")
            
    # Verify SVG fulfillment
    uar = state.get_uar()
    svg_assets = [a for a in uar.assets.values() if "svg" in a.tags]
    
    print(f"SVG Assets Found in UAR: {len(svg_assets)}")
    for asset in svg_assets:
        print(f"  - ID: {asset.id} | Source: {asset.source} | VQA: {asset.vqa_status}")
        abs_path = workspace_path / asset.local_path
        if abs_path.exists():
            print(f"    ✅ Physical file exists: {abs_path}")
        else:
            print(f"    ❌ Physical file MISSING: {abs_path}")

    # Check Markdown for physical write-back
    md_found = False
    for md_file in Path(state.workspace_path).glob("md/*.md"):
        content = md_file.read_text()
        if "<figure" in content and ".svg" in content:
            print(f"✅ Physical Write-back detected in: {md_file.name}")
            md_found = True
            
    if svg_assets and not state.errors and md_found:
        print("
🎉 [E2E TEST] SVG Sub-Agent Integration PASSED.")
    else:
        print("
💀 [E2E TEST] Integration FAILED.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(test_e2e_svg_subagent())
