
import sys
import json
import asyncio
import shutil
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.types import AgentState, Manifest
from src.agents.markdown_qa_agent import MarkdownQAAgent
from src.core.gemini_client import GeminiClient

async def run_full_cycle_test():
    print("\n" + "="*60)
    print("🚦 STARTING COMPREHENSIVE QA CYCLE TEST")
    print("="*60)

    workspace_id = "d2d3d333"
    orig_workspace = Path(f"workspaces/workspace/{workspace_id}")
    
    # We will use distinct workspaces for each scenario to keep them clean
    
    # ==================================================================================
    # SCENARIO A: Happy Path (Expect APPROVE)
    # ==================================================================================
    # print("\n\n" + "-"*40)
    # print("🧪 SCENARIO A: Baseline Check (Happy Path)")
    # print("-"*40)
    # path_a = Path(f"workspaces/workspace/{workspace_id}_cycle_A")
    # setup_workspace(orig_workspace, path_a)
    
    # state_a = load_state(path_a, f"cycle_A_{workspace_id}")
    # client = GeminiClient(timeout=300)
    # qa_agent = MarkdownQAAgent(client=client)
    
    # print("Running QA on original clean data...")
    # state_a = await qa_agent.run(state_a)
    
    # if not state_a.md_qa_needs_revision and not getattr(state_a, 'rewrite_needed', False):
    #      print("✅ Scenario A Passed: Content was APPROVED.")
    # else:
    #      print(f"⚠️ Scenario A Warning: Verdict was not strict APPROVE (Revision: {state_a.md_qa_needs_revision}).")
    
    # ==================================================================================
    # SCENARIO B: Modification Path (Expect MODIFY -> FIXED)
    # ==================================================================================
    print("\n\n" + "-"*40)
    print("🧪 SCENARIO B: Modification Check (Inject Errors)")
    print("-"*40)
    client = GeminiClient(timeout=300)
    qa_agent = MarkdownQAAgent(client=client)

    path_b = Path(f"workspaces/workspace/{workspace_id}_cycle_B")
    setup_workspace(orig_workspace, path_b)
    
    # Inject Typo
    md_file = sorted(path_b.glob("md/*.md"))[0]
    original_text = md_file.read_text()
    # Inject a clear typo
    injected_text = original_text.replace("心电图", "电心图") 
    md_file.write_text(injected_text)
    print(f"  - Injected typo '电心图' into {md_file.name}")
    
    state_b = load_state(path_b, f"cycle_B_{workspace_id}")
    print("Running QA (Expect MODIFY)...")
    state_b = await qa_agent.run(state_b)
    
    # Check Verdict
    if state_b.md_qa_needs_revision and not getattr(state_b, 'rewrite_needed', False):
         print("✅ Critic Verdict: MODIFY (Correct)")
    else:
         print(f"❌ Scenario B Failed Verdict: Expected MODIFY, got Revision={state_b.md_qa_needs_revision}, Rewrite={getattr(state_b, 'rewrite_needed', False)}")
    
    # Check Fix
    new_text = md_file.read_text()
    if "电心图" not in new_text:
        print("✅ Fixer: Successfully fixed typo.")
    else:
        print(f"❌ Fixer: Failed to fix typo. (Count: {new_text.count('电心图')})")

    # ==================================================================================
    # SCENARIO C: Rewrite Path (Expect REWRITE -> RESET)
    # ==================================================================================


# --- Helpers ---

def setup_workspace(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"  - Workspace setup: {dst}")

def load_state(ws_path, job_id):
    manifest = Manifest(**json.loads((ws_path / "manifest.json").read_text()))
    log_data = json.loads((ws_path / "debug_logs/step_001.json").read_text())
    
    md_files = sorted([str(f) for f in ws_path.glob("md/*.md")])
    
    # --- Load Full Raw Materials ---
    inputs_dir = root_dir / "inputs"
    exclude = ["prompt.txt", "slides_task_prompt.txt"]
    all_materials = []
    print("📚 Loading reference materials for QA...")
    for f_path in sorted(inputs_dir.glob("*")):
        if f_path.is_file() and f_path.name not in exclude:
            content = f_path.read_text(encoding="utf-8")
            all_materials.append(f"## Reference: {f_path.name}\n\n{content}")
    
    full_raw = (log_data.get("raw_materials", "") + "\n\n" + "\n\n".join(all_materials)).strip()
    # ------------------------------

    return AgentState(
        job_id=job_id,
        workspace_path=str(ws_path),
        raw_materials=full_raw,
        project_brief=log_data.get("project_brief", ""),
        manifest=manifest,
        completed_md_sections=md_files,
        debug_mode=True
    )

def output_has_chinese(text):
    for char in text:
        if '\u4e00' <= char <= '\u9fff': return True
    return False

if __name__ == "__main__":
    asyncio.run(run_full_cycle_test())
