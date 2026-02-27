import asyncio
import os
import json
from pathlib import Path
from src.core.types import AgentState, Manifest, UniversalAssetRegistry
from src.orchestration.workflow_markdown import create_sota2_workflow
from src.core.gemini_client import GeminiClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def recover_and_run():
    job_id = "v16_comprehensive_run"
    workspace_path = Path("workspace") / job_id
    
    # 1. Load Manifest
    manifest_path = workspace_path / "manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest_data = json.load(f)
        manifest = Manifest(**manifest_data)
    
    # 2. Identify existing MD files
    md_dir = workspace_path / "md"
    completed_md = []
    for section in manifest.sections:
        md_file = md_dir / f"{section.id}.md"
        if md_file.exists():
            completed_md.append(str(md_file))
            section.file_path = str(md_file)
    
    print(f"📦 Recovered {len(completed_md)} Markdown sections.")

    # 3. Initialize State
    user_intent_base = Path("inputs/prompt.txt").read_text(encoding="utf-8")
    user_intent = user_intent_base + """

CRITICAL REQUIREMENT: You MUST design a detailed, multi-section structure with at least 4 deep chapters to cover this topic comprehensively. Ensure high visual density with multiple :::visual directives per chapter."""
    reference_materials = Path("inputs/combined_raw_materials.txt").read_text(encoding="utf-8")

    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent=user_intent,
        reference_materials=reference_materials,
        manifest=manifest,
        completed_md_sections=completed_md,
        current_section_index=len(completed_md),
        markdown_approved=True, 
        uar_path=str(workspace_path / "assets.json"),
        debug_mode=True
    )
    
    db_path = workspace_path / "checkpoints.db"
    if db_path.exists():
        db_path.unlink()
        
    client = GeminiClient()
    
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        app = create_sota2_workflow(
            client=client,
            checkpointer=checkpointer
        )
        
        config = {"configurable": {"thread_id": job_id}}
        
        # --- SEEDING LOGIC ---
        # 1. Update state to set the initial data
        await app.aupdate_state(config, state.model_dump(), as_node="markdown_review")
        
        print(f"🚀 State seeded. Resuming from 'markdown_review' transition...")
        
        # 2. Resume from the seeded state
        # The graph will evaluate the conditional edges from 'markdown_review' 
        # which should lead to 'batch_fulfillment'
        async for event in app.astream(None, config=config, stream_mode="values"):
            # Progress will be visible in console
            pass

    print("\n✅ Recovery run finished.")

if __name__ == "__main__":
    asyncio.run(recover_and_run())
