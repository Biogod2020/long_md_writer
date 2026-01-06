import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest
from src.agents.markdown_qa_agent import MarkdownQAAgent

def debug_markdown_qa():
    """
    Standardize the test by using an existing workspace.
    """
    print("=== Markdown QA Debugger ===")
    
    # 1. Configuration
    api_url = os.getenv("API_URL", "http://localhost:8888/v1")
    workspace_id = "d2d3d333" # Using the one from previous run
    workspace_path = root_dir / "workspace" / workspace_id
    
    if not workspace_path.exists():
        print(f"Error: Workspace {workspace_path} not found.")
        return

    # 2. Initialize Client
    client = GeminiClient(api_base_url=api_url, timeout=300)
    
    # 3. Load Manifest
    manifest_path = workspace_path / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest = Manifest(**manifest_data)
    
    # 4. Construct State
    # Note: We need real brief for the critic to work accurately
    # The architect agent saves the brief in manifest.description usually? 
    # Actually AgentState has project_brief. Let's try to extract it from manifest or use a placeholder.
    # In this repo, manifest.description often contains the SOTA spec.
    
    state = AgentState(
        job_id=f"debug-{workspace_id}",
        workspace_path=str(workspace_path),
        manifest=manifest,
        project_brief=manifest.description, # Using description as brief for testing
        raw_materials="Simulated raw materials based on ECG Physics.",
        completed_md_sections=[
            str(workspace_path / "md" / f"mod-0{i}.md") for i in range(1, 6)
        ],
        debug_mode=True
    )

    # 5. Run QA Agent
    agent = MarkdownQAAgent(client, max_iterations=1) # Just one iteration for debugging
    
    print(f"Reviewing {len(state.completed_md_sections)} sections...")
    try:
        new_state = agent.run(state)
        print("\n=== Result ===")
        print(f"QA Iterations: {new_state.md_qa_iterations}")
        print(f"Needs Revision: {new_state.md_qa_needs_revision}")
        if new_state.errors:
            print(f"Errors encountered: {new_state.errors}")
    except Exception as e:
        print(f"\nFailed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_markdown_qa()
