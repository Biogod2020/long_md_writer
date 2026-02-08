
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

async def run_complex_loop_test():
    print("\n" + "="*60)
    print("🚦 STARTING COMPLEX QA LOOP TEST (KNOWLEDGE GAP)")
    print("="*60)

    workspace_id = "complex_loop_test"
    # Use the existing d2d3d333 workspace as a base (it was generated for the 12-lead chapter)
    base_ws = Path("workspaces/workspace/e2e_test_scratch/8bbdfd91")
    if not base_ws.exists():
        # Fallback to a wider search if the ID changed
        base_ws = next(Path("workspace").glob("8*"), None)
    
    if not base_ws:
        print("❌ Error: Could not find a base workspace to test on.")
        return

    test_ws = Path(f"workspaces/workspace/{workspace_id}")
    if test_ws.exists():
        shutil.rmtree(test_ws)
    shutil.copytree(base_ws, test_ws)
    print(f"  - Test Workspace: {test_ws}")

    # --- INJECT KNOWLEDGE GAP ---
    # In phase-01.md, we remove the KCL derivation.
    md_file = test_ws / "md/phase-01.md"
    content = md_file.read_text()
    
    # Locate the KCL section and gut it
    gap_pattern = r"### 数学推导：基尔霍夫电流定律 \(KCL\) 的应用.*?\n\n###"
    import re
    gutted_content = re.sub(gap_pattern, "### 数学推导：基尔霍夫电流定律 (KCL) 的应用\n\n本节我们将探讨 WCT 的数学原理。通过基础电路分析，我们可以得出 WCT 的电势接近于零。\n\n###", content, flags=re.DOTALL)
    
    if content == gutted_content:
        # Alt pattern if the first one fails
        gap_pattern = r"### 数学推导：.*?（KCL）.*?应用.*?\n\n###"
        gutted_content = re.sub(gap_pattern, "### 数学推导：基尔霍夫电流定律 (KCL) 的应用\n\n本节我们将探讨 WCT 的数学原理。通过基础电路分析，我们可以得出 WCT 的电势接近于零。\n\n###", content, flags=re.DOTALL)

    md_file.write_text(gutted_content)
    print("  - [Gap Injected] Removed KCL derivation equations and detailed steps from phase-01.md")

    # --- LOAD STATE ---
    manifest_data = json.loads((test_ws / "manifest.json").read_text())
    manifest = Manifest(**manifest_data)
    
    # Mock project brief from logs if available
    brief = ""
    log_file = next(test_ws.glob("debug_logs/step_*.json"), None)
    if log_file:
        log_data = json.loads(log_file.read_text())
        brief = log_data.get("project_brief", "")

    state = AgentState(
        job_id=workspace_id,
        workspace_path=str(test_ws),
        raw_materials="The user wants a deep dive into ECG leads physics. Chapter 2 must cover WCT, Einthoven, and Goldberger with KCL derivations.",
        project_brief=brief,
        manifest=manifest,
        completed_md_sections=[str(f) for f in sorted(test_ws.glob("md/*.md"))],
        debug_mode=True
    )

    # --- RUN LOOP ---
    client = GeminiClient(timeout=300) # Use actual client
    qa_agent = MarkdownQAAgent(client=client, max_iterations=3)

    print("\n--- Starting Iterative QA Loop ---")
    
    max_test_iters = 3
    for i in range(max_test_iters):
        print(f"\n[Test Iteration {i+1}/{max_test_iters}]")
        state = await qa_agent.run(state)
        
        if state.markdown_approved:
            print(f"\n✅ SUCCESS: Content approved after {state.md_qa_iterations} iterations.")
            break
        
        if getattr(state, "rewrite_needed", False):
            print("\n🚨 REWRITE TRIGGERED (Major failure). Test stopped.")
            break
            
        if not state.md_qa_needs_revision:
            print("\n⚠️ LOOP STOPPED: No further revisions suggested by Advicer/Fixer.")
            break

    # --- FINAL VERIFICATION ---
    final_content = md_file.read_text()
    if "\\Phi_{WCT}" in final_content and "\sum I = 0" in final_content:
        print("\n✅ VERIFICATION PASSED: The KCL equations were successfully restored by the Fixer.")
    else:
        print("\n❌ VERIFICATION FAILED: The KCL equations are still missing.")
        print("-" * 20)
        # print("Final Content Snippet:")
        # print(final_content[final_content.find("数学推导"): final_content.find("数学推导") + 500])

if __name__ == "__main__":
    # Ensure workspace directory exists
    Path("workspace").mkdir(exist_ok=True)
    asyncio.run(run_complex_loop_test())
