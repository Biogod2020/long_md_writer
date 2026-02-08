import os
import json
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest
from src.orchestration.workflow import create_generation_workflow

def resume_production_test(workspace_dir: str):
    workspace_path = Path(workspace_dir)
    if not workspace_path.exists():
        print(f"Error: {workspace_dir} does not exist.")
        return

    # 1. Configuration
    api_base_url = "http://localhost:7860"
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    # 2. Load Manifest
    manifest_path = workspace_path / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: No manifest.json found in {workspace_dir}")
        return
    
    with open(manifest_path, "r") as f:
        manifest_data = json.load(f)
        manifest = Manifest(**manifest_data)
    
    # 3. Load Style Mapping
    # Find style_mapping in assets or root
    mapping_path = workspace_path / "style_mapping.json"
    from src.core.types import StyleMapping
    if mapping_path.exists():
        with open(mapping_path, "r") as f:
            mapping_data = json.load(f)
            style_mapping = StyleMapping(**mapping_data)
    else:
        # If design didn't finish, we might need to rerun it, or just use empty
        style_mapping = None

    # 4. Find completed sections
    md_sections = sorted([str(p) for p in (workspace_path / "md").glob("sec-*.md")], key=lambda x: int(Path(x).stem.split("-")[1]))
    html_sections = sorted([str(p) for p in (workspace_path / "html").glob("sec-*.html")], key=lambda x: int(Path(x).stem.split("-")[1]))
    
    # 5. Initialize State
    job_id = workspace_path.name
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        manifest=manifest,
        style_mapping=style_mapping,
        completed_md_sections=md_sections,
        completed_html_sections=html_sections
    )
    
    print(f"Resuming production for {job_id}...")
    print(f"Completed MD: {len(md_sections)}")
    print(f"Completed HTML: {len(html_sections)}")
    
    # 6. Run Workflow
    workflow = create_generation_workflow(client)
    app = workflow.compile()
    
    # The workflow starts at 'writer', so it will check if all sections are written.
    # Since completed_md_sections is full, it will jump to 'design' or 'transformer'.
    
    result = app.invoke(state.model_dump())
    final_state = AgentState(**result)
    
    if final_state.errors:
        print("\nRESUME FAILED:")
        for err in final_state.errors:
            print(f"  - {err}")
    else:
        print("\nRESUME SUCCESSFUL!")
        print(f"Final HTML: {final_state.final_html_path}")

if __name__ == "__main__":
    import sys
    # Usage: python resume_production_test.py workspaces/workspace/sota_prod_3522
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "workspaces/workspace/sota_prod_3522"
    resume_production_test(target_dir)
