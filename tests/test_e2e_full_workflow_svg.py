"""
Full E2E Test for SOTA 2.0 Workflow with SVG Sub-Agent
Uses real project inputs: prompt.txt and combined_raw_materials.txt
"""

import asyncio
import os
import shutil
from pathlib import Path
from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.types import AssetSource, AssetVQAStatus

async def test_full_e2e_with_svg_subagent():
    print("\n🚀 [FULL E2E TEST] Starting SOTA 2.0 Workflow...")
    
    # 1. Load Real Inputs
    prompt_path = Path("inputs/prompt.txt")
    raw_materials_path = Path("inputs/combined_raw_materials.txt")
    
    if not prompt_path.exists() or not raw_materials_path.exists():
        print("❌ Error: Missing input files in 'inputs/' directory.")
        return

    user_intent = prompt_path.read_text(encoding="utf-8")
    reference_materials = raw_materials_path.read_text(encoding="utf-8")
    
    job_id = "full_e2e_svg_test"
    workspace_base = "data/test_artifacts/full_e2e"
    workspace_path = Path(workspace_base) / job_id
    
    # Clean up previous run
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    print(f"📍 Workspace: {workspace_path}")
    print(f"🎯 Intent Length: {len(user_intent)} chars")
    print(f"📚 Reference Length: {len(reference_materials)} chars")

    # 2. Execute Workflow
    # We use auto_mode=True to handle all approval gates automatically
    state = await run_sota2_workflow(
        user_intent=user_intent,
        reference_materials=reference_materials,
        workspace_base=workspace_base,
        job_id=job_id,
        auto_mode=True,
        debug_mode=True
    )
    
    # 3. Comprehensive Verification
    print("\n--- [E2E VERIFICATION REPORT] ---")
    print(f"Job Status: {'SUCCESS' if not state.errors else 'FAILED'}")
    
    if state.errors:
        print("❌ Errors detected:")
        for err in state.errors:
            print(f"  - {err}")
            
    uar = state.get_uar()
    assets = list(uar.assets.values())
    
    svg_assets = [a for a in assets if "svg" in a.tags]
    web_assets = [a for a in assets if a.source == AssetSource.WEB]
    
    print("\n📊 Asset Statistics:")
    print(f"  - Total Assets in UAR: {len(assets)}")
    print(f"  - SVG Assets (via SVGAgent): {len(svg_assets)}")
    print(f"  - Web Assets (via ImageSourcingAgent): {len(web_assets)}")
    
    # Validation A: SVG Fulfillment
    print("\n🔍 Validating SVG Assets:")
    for a in svg_assets:
        abs_p = workspace_path / a.local_path
        exists = abs_p.exists()
        print(f"  - [{a.id}] {a.semantic_label[:50]}... | File: {exists} | VQA: {a.vqa_status}")
        if exists:
            content = abs_p.read_text()
            if "<svg" in content and "</svg>" in content:
                print("    ✅ Valid SVG syntax confirmed.")
            else:
                print("    ❌ Corrupted SVG file.")

    # Validation B: Web Sourcing Fulfillment
    print("\n🔍 Validating Web Sourced Assets:")
    for a in web_assets:
        abs_p = workspace_path / a.local_path
        exists = abs_p.exists()
        print(f"  - [{a.id}] {a.semantic_label[:50]}... | File: {exists} | VQA: {a.vqa_status}")
        if exists:
            size = abs_p.stat().st_size
            print(f"    ✅ Image downloaded successfully ({size/1024:.1f} KB)")

    # Validation C: Physical Write-back
    print("\n🔍 Validating Markdown Physical Write-back:")
    md_files = list(Path(state.workspace_path).glob("md/*.md"))
    write_back_success = False
    for md in md_files:
        content = md.read_text()
        if "<figure" in content and "data-asset-id" in content:
            print(f"  ✅ Write-back confirmed in {md.name}")
            write_back_success = True
            
    # Final Score
    if not state.errors and len(svg_assets) > 0 and len(web_assets) >= 2 and write_back_success:
        print("\n🏆 [FULL E2E RESULT] SOTA 2.0 WORKFLOW PASSED.")
        print("The new SVGAgent and Reflection Loop are fully operational and integrated.")
    else:
        print("\n❌ [FULL E2E RESULT] WORKFLOW FAILED TO MEET CRITERIA.")
        exit(1)

if __name__ == "__main__":
    # Setup loop
    asyncio.run(test_full_e2e_with_svg_subagent())
