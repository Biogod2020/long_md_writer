"""
Final Verification E2E - v18 (Comprehensive Stress Test)
Using v12 inputs (Deep technical writing + Mixed assets) 
to verify the integrated robustness of Shift-Left Editorial + ID-Based Fulfillment + Provider Polling.
"""

import asyncio
import os
import shutil
import json
from pathlib import Path
from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.types import AssetSource

async def run_verification_v18():
    # SOTA: v18 ID for this specific run
    job_id = "v18_comprehensive_run"
    workspace_base = "workspace"
    workspace_path = Path(workspace_base) / job_id

    # SOTA: RESUME MODE ENABLED
    if workspace_path.exists():
        print(f"🔄 Workspace found. Resuming E2E Run: {job_id}")
    else:
        print(f"🚀 [VERIFICATION v18] Starting FRESH E2E Run: {job_id}")
    
    # 1. Load Real v12 Inputs
    try:
        prompt_path = Path("inputs/prompt.txt")
        raw_materials_path = Path("inputs/combined_raw_materials.txt")
        
        user_intent = prompt_path.read_text(encoding="utf-8")
        # SOTA: Force multi-section structure for extreme stress testing (Matches v16/v12 requirement)
        user_intent += "\n\nCRITICAL REQUIREMENT: You MUST design a detailed, multi-section structure with at least 4 deep chapters to cover this topic comprehensively. Ensure high visual density with multiple :::visual directives per chapter."
        reference_materials = raw_materials_path.read_text(encoding="utf-8")
        print("✅ v12 Inputs loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load inputs: {e}")
        return
    
    print(f"📍 Target Workspace: {workspace_path.absolute()}")

    # 2. Execute Workflow in Auto-Mode
    print("⚙️  Initiating SOTA 2.1 Pipeline (Shift-Left Editorial Mode + Multi-Provider Polling)...")
    state = await run_sota2_workflow(
        user_intent=user_intent,
        reference_materials=reference_materials,
        workspace_base=workspace_base,
        job_id=job_id,
        auto_mode=True,
        debug_mode=True
    )
    
    # 3. Quality Audit Report
    print("\n" + "="*50)
    print("📊 VERIFICATION v18 FINAL AUDIT REPORT")
    print("="*50)
    
    uar_path = workspace_path / "assets.json"
    svg_count = 0
    web_count = 0
    if uar_path.exists():
        try:
            with open(uar_path, 'r') as f:
                uar_data = json.load(f)
                assets_dict = uar_data.get("assets", {})
                for a in assets_dict.values():
                    tags = a.get("tags", [])
                    source = str(a.get("source", "")).upper()
                    if "svg" in [t.lower() for t in tags]:
                        svg_count += 1
                    if "WEB" in source:
                        web_count += 1
        except Exception as e:
            print(f"⚠️ Error reading UAR: {e}")
    
    print(f"Status: {'✅ SUCCESS' if not state.errors else '❌ FAILED'}")
    print(f"Chapters Generated: {len(state.completed_md_sections)}")
    print(f"Physical SVG Assets: {svg_count}")
    print(f"Physical Web Assets: {web_count}")
    
    # Verify that NO :::visual or :::script remain in the final document
    merged_path = workspace_path / "final_full.md"
    all_fulfilled = False
    if merged_path.exists():
        content = merged_path.read_text(encoding="utf-8")
        unfulfilled = content.count(":::visual") + content.count(":::script")
        print(f"Unfulfilled Directives: {unfulfilled}")
        if unfulfilled == 0:
            all_fulfilled = True

    if not state.errors and (svg_count > 0 or web_count > 0) and all_fulfilled:
        print("\n🏆 [VERIFICATION v18] COMPREHENSIVE RUN PASSED.")
    else:
        print("\n💀 [VERIFICATION v18] FAILED or UNFULFILLED. Check logs for details.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(run_verification_v18())
