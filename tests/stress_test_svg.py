import asyncio
import json
import shutil
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient

async def stress_test_svg():
    print("🔥 [STRESS TEST] Starting SVG QA Loop Stress Test...")
    
    job_id = "stress_svg_qa"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    md_dir = workspace_path / "md"
    md_dir.mkdir()
    (workspace_path / "agent_generated").mkdir()
    
    # Create a section with a VERY complex SVG request to trigger repairs
    md_path = md_dir / "s1-svg-test.md"
    content = """# SVG Stress Test
:::visual {"id": "s1-fig-complex-vector", "action": "GENERATE_SVG", "description": "A highly detailed 3D vector diagram of the heart heart with overlapping labels for ALL 12 leads, coronary arteries (LAD, RCA, LCX), and electrical dipole vectors. Ensure no labels overlap and all technical details are mathematically perfect."}
Test content.
:::
"""
    md_path.write_text(content)

    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent="Stress test the SVG repair loop.",
        manifest=Manifest(project_title="SVG Stress", description="Test", sections=[
            SectionInfo(id="s1-svg-test", title="SVG Stress", summary="Test")
        ]),
        completed_md_sections=[str(md_path)]
    )
    
    client = GeminiClient()
    agent = AssetFulfillmentAgent(client=client, debug=True)
    
    print("\n🚀 Starting parallel fulfillment...")
    await agent.run_parallel_async(state)
    
    print("\n✨ [STRESS TEST] Completed.")

if __name__ == "__main__":
    asyncio.run(stress_test_svg())