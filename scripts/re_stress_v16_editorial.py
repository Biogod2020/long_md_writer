import asyncio
import json
import os
import shutil
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.editorial_qa_agent import EditorialQAAgent
from src.core.types import AgentState, Manifest, SectionInfo, UniversalAssetRegistry
from src.core.gemini_client import GeminiClient
from src.agents.editorial_qa.critic import run_editorial_critic
from src.agents.editorial_qa.advicer import run_editorial_advicer
from src.agents.markdown_qa.fixer import run_markdown_fixer, apply_patches
from src.core.merger import merge_markdown_sections
from src.core.validators import MarkdownValidator, ValidationSeverity

async def run_enhanced_stress_test():
    source_ws = Path("workspace/v16_comprehensive_run")
    target_ws = Path("workspace/v16_editorial_stress_rerun")
    target_ws.mkdir(parents=True, exist_ok=True)
    log_dir = target_ws / "editorial_qa_logs"
    log_dir.mkdir(exist_ok=True)
    
    print(f"🚀 Initializing Enhanced Editorial Stress Test (v16 rerun)")
    
    # 1. Prepare Workspace
    for f in ["manifest.json", "assets.json"]:
        if (source_ws / f).exists():
            shutil.copy(source_ws / f, target_ws / f)
            
    md_dir = target_ws / "md"
    md_dir.mkdir(exist_ok=True)
    for f in (source_ws / "md").glob("*.md"):
        shutil.copy(f, md_dir / f.name)

    # 2. Setup State
    with open(target_ws / "manifest.json", 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
    
    sections = [SectionInfo(**s) for s in manifest_data['sections']]
    manifest = Manifest(
        project_title=manifest_data['project_title'],
        description=manifest_data['description'],
        sections=sections
    )
    
    section_paths = [str(f) for f in sorted(md_dir.glob("*.md"))]
    state = AgentState(
        job_id="v16_stress_rerun",
        workspace_path=str(target_ws),
        completed_md_sections=section_paths,
        debug_mode=True
    )
    state.manifest = manifest
    if (target_ws / "assets.json").exists():
        state.asset_registry = UniversalAssetRegistry.load_from_file(str(target_ws / "assets.json"))

    # 3. Manual Loop to Capture EVERYTHING
    client = GeminiClient()
    validator = MarkdownValidator()
    merged_path = target_ws / "final_full.md"
    
    print(f"  [Step 1] Performing Physical Merge...")
    merge_markdown_sections(
        state.completed_md_sections, 
        str(merged_path.absolute()), 
        workspace_path=str(target_ws), 
        asset_registry=state.get_uar()
    )
    
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"\n🔥 [Iteration {iteration}/{max_iterations}]")
        
        current_content = merged_path.read_text(encoding="utf-8")
        # Save snapshot of content before this iteration's fix
        (log_dir / f"content_pre_it{iteration}.md").write_text(current_content, encoding="utf-8")
        
        # --- PHASE 1: MECHANICAL ---
        print("  [Phase 1] Static Validation...")
        validation = validator.validate_all(current_content)
        (log_dir / f"validation_it{iteration}.json").write_text(
            json.dumps([i.message for i in validation.issues], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        
        # --- PHASE 2-4: CRITIC ---
        print("  [Phase 2] Running Critic...")
        critique = await run_editorial_critic(client, state, current_content, debug=True)
        (log_dir / f"critique_it{iteration}.json").write_text(
            json.dumps(critique, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        
        if critique.get("verdict") == "APPROVE":
            print("  ✅ Document APPROVED by Critic.")
            break
            
        # --- ADVICER ---
        print("  [Phase 3] Generating Advice (Quota: 5)...")
        advice_map = await run_editorial_advicer(client, current_content, critique.get("feedback", ""), debug=True)
        (log_dir / f"advice_it{iteration}.json").write_text(
            json.dumps(advice_map, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        
        if not advice_map or "final_full.md" not in advice_map:
            print("  ⚠️ No advice generated.")
            break
            
        # --- FIXER ---
        print("  [Phase 4] Applying Patches...")
        advice = advice_map["final_full.md"]
        fix_result = await run_markdown_fixer(client, current_content, advice, debug=True)
        (log_dir / f"fix_result_it{iteration}.json").write_text(
            json.dumps(fix_result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        
        if fix_result and fix_result.get("status") == "FIXED":
            new_content = apply_patches(current_content, fix_result)
            merged_path.write_text(new_content, encoding="utf-8")
            print(f"  ✅ Applied {len(fix_result.get('patches', []))} patches.")
        else:
            print(f"  ❌ Fixer failed.")
            break

    print(f"\n🏁 Stress Test Rerun Complete. All logs in: {log_dir}")

if __name__ == "__main__":
    asyncio.run(run_enhanced_stress_test())
