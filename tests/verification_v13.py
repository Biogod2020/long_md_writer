"""
Final Verification E2E - v13 (Fresh Run)
Testing SOTA 2.0 Full Pipeline from scratch.
Focus: Global Gatekeeper, Multi-modal Alignment, and Fresh Persistence.
"""

import asyncio
import os
import shutil
import json
from pathlib import Path
from src.orchestration.workflow_markdown import run_sota2_workflow
from src.core.types import AssetSource

async def run_verification_v13():
    # SOTA Resume Logic: Use a stable job_id to allow checkpoint resume
    job_id = "v13_fresh_full_sync"
    workspace_base = "workspace"
    workspace_path = Path(workspace_base) / job_id

    if workspace_path.exists():
        print(f"🚀 [VERIFICATION v13] Resuming Existing E2E Run: {job_id}")
    else:
        print(f"🚀 [VERIFICATION v13] Starting FRESH E2E Run: {job_id}")
    
    # 1. Load Real Inputs
    try:
        prompt_path = Path("inputs/prompt.txt")
        raw_materials_path = Path("inputs/combined_raw_materials.txt")
        
        user_intent = prompt_path.read_text(encoding="utf-8")
        # SOTA: Add high-complexity requirement for v13
        user_intent += "\n\n[STRESS TEST REQUIREMENT]:\n1. You MUST generate a multi-layered MERMAID flowchart for diagnostic logic.\n2. You MUST generate at least 2 highly detailed SVG diagrams for vector logic.\n3. Ensure 4+ sections."
        
        reference_materials = raw_materials_path.read_text(encoding="utf-8")
        print("✅ Inputs loaded and stress-injected.")
    except Exception as e:
        print(f"❌ Failed to load inputs: {e}")
        return
    
    print(f"📍 Target Workspace: {workspace_path.absolute()}")

    # 2. Execute Workflow in Auto-Mode
    print("⚙️  Initiating SOTA 2.0 Pipeline (Zero-State)...")
    state = await run_sota2_workflow(
        user_intent=user_intent,
        reference_materials=reference_materials,
        workspace_base=workspace_base,
        job_id=job_id,
        auto_mode=True, 
        debug_mode=True
    )
    
    # 3. Final Audit Report
    print("\n" + "="*50)
    print("📊 VERIFICATION v13 FINAL AUDIT REPORT")
    print("="*50)
    
    uar_path = workspace_path / "assets.json"
    svg_count = 0
    web_count = 0
    mermaid_count = 0
    
    if uar_path.exists():
        with open(uar_path, 'r') as f:
            uar_data = json.load(f)
            assets = uar_data.get("assets", {})
            for a in assets.values():
                tags = [t.lower() for t in a.get("tags", [])]
                if "svg" in tags: svg_count += 1
                if "mermaid" in tags: mermaid_count += 1
                if str(a.get("source", "")).upper() == "WEB": web_count += 1
    
    print(f"Status: {'✅ SUCCESS' if not state.errors else '❌ FAILED'}")
    print(f"Total Sections Written: {len(state.completed_md_sections)}")
    print(f"Physical SVG Assets: {svg_count}")
    print(f"Physical Web Assets: {web_count}")
    print(f"Mermaid Diagrams: {mermaid_count}")
    
    # 4. Global Gatekeeper Audit
    qa_log_dir = workspace_path / "editorial_qa_logs"
    if qa_log_dir.exists():
        critiques = list(qa_log_dir.glob("critique_it*.json"))
        print(f"Editorial QA Cycles: {len(critiques)}")
    else:
        print("❌ Editorial QA logs missing!")

    # 5. Caption Alignment Check
    md_verified = False
    for md_file in (workspace_path / "md").glob("*.md"):
        content = md_file.read_text()
        if "<figcaption>" in content:
            md_verified = True
            
    if not state.errors and md_verified and (svg_count + web_count + mermaid_count) > 0:
        print("\n🏆 [VERIFICATION v13] PASSED SUCCESSFULLY.")
    else:
        print("\n💀 [VERIFICATION v13] FAILED CRITERIA.")
        exit(1)

if __name__ == "__main__":
    asyncio.run(run_verification_v13())
