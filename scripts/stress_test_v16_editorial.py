import asyncio
import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.editorial_qa_agent import EditorialQAAgent
from src.core.types import AgentState, Manifest, SectionInfo, UniversalAssetRegistry
from src.core.gemini_client import GeminiClient

async def main():
    workspace = Path("workspace/v16_stress_test").resolve()
    manifest_path = workspace / "manifest.json"
    assets_path = workspace / "assets.json"
    merged_path = workspace / "final_full.md"
    
    if not manifest_path.exists():
        print(f"❌ Missing manifest in {workspace}")
        return

    # 1. Load Context
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
    
    # Reconstruct manifest objects
    sections = [SectionInfo(**s) for s in manifest_data['sections']]
    manifest = Manifest(
        project_title=manifest_data['project_title'],
        description=manifest_data['description'],
        sections=sections
    )
    
    # 2. Setup State
    # We point to the sections in the md/ folder
    section_files = sorted(list((workspace / "md").glob("s*-sec-*.md")))
    section_paths = [str(f) for f in section_files]
    
    state = AgentState(
        job_id="v16_stress_test",
        workspace_path=str(workspace),
        completed_md_sections=section_paths
    )
    state.manifest = manifest
    
    if assets_path.exists():
        state.asset_registry = UniversalAssetRegistry.load_from_file(str(assets_path))
    
    # 3. Initialize Agent
    # We increase max_iterations to see how it handles cumulative fixes
    client = GeminiClient()
    agent = EditorialQAAgent(client=client, max_iterations=5, strict_mode=True)
    
    print(f"\n🚀 Starting Large-Scale Stress Test on v16 artifacts...")
    print(f"📂 Sections: {len(section_paths)}")
    
    # 4. Run Stress Test
    try:
        final_state = await agent.run_async(state)
        
        print("\n✅ Stress Test Completed.")
        print(f"📊 Approved: {final_state.markdown_approved}")
        
        # Check logs
        log_dir = workspace / "editorial_qa_logs"
        if log_dir.exists():
            print(f"\n🔍 Audit Logs in {log_dir}:")
            for log_file in sorted(log_dir.glob("*.json")):
                print(f"  - {log_file.name}")
            for thinking_file in sorted(log_dir.glob("thinking_*.txt")):
                print(f"  - {thinking_file.name}")
                
    except Exception as e:
        import traceback
        print(f"\n❌ Stress Test CRASHED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
