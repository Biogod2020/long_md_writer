
import sys
import os
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

async def run_real_qa_verification():
    print("\n" + "="*50)
    print("🚀 STARTING REAL QA VERIFICATION (Workspace d2d3d333)")
    print("="*50)

    workspace_id = "d2d3d333"
    orig_workspace = Path(f"workspace/{workspace_id}")
    test_workspace = Path(f"workspace/{workspace_id}_test_qa")
    
    # 1. Create a temporary copy of the workspace so we don't mess up original data
    if test_workspace.exists():
        shutil.rmtree(test_workspace)
    shutil.copytree(orig_workspace, test_workspace)
    print(f"✅ Created test copy: {test_workspace}")

    # 2. Load Manifest
    manifest_path = test_workspace / "manifest.json"
    manifest = None
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text())
            manifest = Manifest(**manifest_data)
            print(f"✅ Loaded Manifest: {manifest.project_title}")
        except Exception as e:
            print(f"❌ Error loading manifest: {e}")
            return

    # 3. Load Raw Materials from log
    log_path = test_workspace / "debug_logs/step_001.json"
    raw_materials = ""
    project_brief = ""
    if log_path.exists():
        try:
            log_data = json.loads(log_path.read_text())
            raw_materials = log_data.get("raw_materials", "")
            project_brief = log_data.get("project_brief", "")
            print(f"✅ Loaded context from log (Raw: {len(raw_materials)} chars)")
        except Exception as e:
            print(f"❌ Error loading log data: {e}")

    # 4. Populate Completed Sections
    md_dir = test_workspace / "md"
    completed_md = []
    if md_dir.exists():
        # Important: use sorted glob to maintain order
        for md_file in sorted(md_dir.glob("*.md")):
            completed_md.append(str(md_file))
    
    print(f"✅ Found {len(completed_md)} Markdown sections.")

    # 5. Initialize State
    state = AgentState(
        job_id=f"verify_{workspace_id}",
        workspace_path=str(test_workspace),
        raw_materials=raw_materials,
        project_brief=project_brief,
        manifest=manifest,
        completed_md_sections=completed_md
    )
    state.debug_mode = True

    # 6. Run Agent
    api_url = os.getenv("API_URL", "http://localhost:8888/v1")
    client = GeminiClient(api_base_url=api_url, timeout=300)
    agent = MarkdownQAAgent(client=client)

    print("\n--- Running MarkdownQAAgent.run() ---")
    try:
        final_state = await agent.run(state)
        print("\n" + "="*50)
        print("📊 VERIFICATION RESULTS")
        print(f"Verdict Status: {final_state.md_qa_needs_revision}")
        if getattr(final_state, 'rewrite_needed', False):
            print("Rewrite Triggered: YES")
            print(f"Feedback Summary: {getattr(final_state, 'rewrite_feedback', '')[:200]}...")
        else:
            print("Rewrite Triggered: NO")
            
        # Check if files changed
        print("\nChecking for file changes...")
        for i, original_v in enumerate(completed_md):
            orig_path = Path(original_v)
            # Find the original corresponding file in the real workspace to compare
            real_orig_path = orig_workspace / "md" / orig_path.name
            if real_orig_path.exists():
                if real_orig_path.read_text() != orig_path.read_text():
                    print(f"📝 CHANGED: {orig_path.name}")
                else:
                    print(f"➖ UNCHANGED: {orig_path.name}")
        
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_real_qa_verification())
