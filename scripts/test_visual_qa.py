"""
Test VisualQA Agent Standalone
Tests the Critic-Fixer dual-agent architecture.
"""

import os
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, StyleMapping
from src.agents.visual_qa import VisualQAAgent

def test_visual_qa():
    # Use the debug workspace from the last run
    workspace_path = Path("workspaces/workspace_debug/debug_201956")
    
    if not workspace_path.exists():
        print(f"❌ Workspace not found: {workspace_path}")
        return
    
    print(f"🔍 Testing VisualQA on: {workspace_path}")
    
    # Setup client
    api_base_url = "http://localhost:7860"
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    # Load manifest
    import json
    manifest_path = workspace_path / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = Manifest(**manifest_data)
    
    # Load style mapping
    style_mapping_path = workspace_path / "style_mapping.json"
    style_mapping_data = json.loads(style_mapping_path.read_text(encoding="utf-8"))
    style_mapping = StyleMapping(**style_mapping_data)
    
    # Build state
    html_files = sorted((workspace_path / "html").glob("sec-*.html"))
    
    state = AgentState(
        job_id="vqa_test",
        workspace_path=str(workspace_path),
        manifest=manifest,
        style_mapping=style_mapping,
        completed_html_sections=[str(f) for f in html_files],
        final_html_path=str(workspace_path / "final.html"),
        vqa_iterations=0
    )
    
    print(f"📄 Final HTML: {state.final_html_path}")
    print(f"📁 HTML Sections: {len(state.completed_html_sections)}")
    
    # Run VQA
    vqa = VisualQAAgent(client=client, debug=True, headless=True)
    
    print("\n🚀 Starting VisualQA...")
    result = vqa.run(state)
    
    print("\n" + "="*50)
    print(f"VQA Iterations: {result.vqa_iterations}")
    print(f"Needs Reassembly: {result.vqa_needs_reassembly}")
    print(f"Errors: {result.errors}")
    print("="*50)
    
    # Check if screenshot was saved
    assets_dir = workspace_path / "assets"
    screenshots = list(assets_dir.glob("vqa_*.jpg"))
    if screenshots:
        print(f"📸 Screenshots saved: {[s.name for s in screenshots]}")
    else:
        print("❌ No screenshots found!")

if __name__ == "__main__":
    test_visual_qa()
