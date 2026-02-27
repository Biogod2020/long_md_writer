
import asyncio
import os
import json
from pathlib import Path
from src.core.types import AgentState, Manifest
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient

async def fulfill_clean():
    job_id = "v16_comprehensive_run"
    workspace_path = Path("workspace") / job_id
    
    # 1. Load Manifest
    manifest_path = workspace_path / "manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
        manifest = Manifest(**manifest_data)
    
    # 2. Identify MD files
    md_dir = workspace_path / "md"
    completed_md = []
    for section in manifest.sections:
        md_file = md_dir / f"{section.id}.md"
        if md_file.exists():
            completed_md.append(str(md_file))
    
    # 3. Create State
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        manifest=manifest,
        completed_md_sections=completed_md,
        uar_path=str(workspace_path / "assets.json"),
        debug_mode=True
    )
    
    # 4. Initialize Fulfillment Agent
    # SOTA: Headless=True for stability, but Solution A/B are active
    agent = AssetFulfillmentAgent(
        client=GeminiClient(),
        max_concurrency=5,
        headless=True
    )
    
    print(f"🚀 [CLEAN FULFILLMENT] Starting for {len(completed_md)} sections...")
    await agent.run_parallel_async(state)
    
    print("\n✅ Clean-room fulfillment finished.")

if __name__ == "__main__":
    asyncio.run(fulfill_clean())
