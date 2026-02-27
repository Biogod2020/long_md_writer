import asyncio
from pathlib import Path
from src.orchestration.workflow_markdown import create_sota2_workflow
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def production_loop(job_id: str):
    workspace_path = Path(f"workspace/{job_id}")
    db_path = workspace_path / "checkpoints.db"
    
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        client = GeminiClient()
        app = create_sota2_workflow(client=client, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": job_id}}
        
        while True:
            state_info = await app.aget_state(config)
            next_node = state_info.next[0] if state_info.next else None
            
            if not next_node:
                print("🏁 Production Finished.")
                break
                
            if next_node == "markdown_review":
                print(f"✅ Auto-approving section review...")
                await app.aupdate_state(config, {"markdown_approved": True})
            elif next_node == "batch_asset_review":
                print("🏁 Reached Asset Review phase. Stopping for final audit.")
                break
            else:
                print(f"⏳ Resuming node: {next_node}...")
            
            # Resume execution
            async for event in app.astream(None, config=config, stream_mode="values"):
                if isinstance(event, dict):
                    idx = event.get("current_section_index", 0)
                    print(f"  [Progress] Working on Section {idx+1}...", end="\r")

if __name__ == "__main__":
    job_id = "sota2_20260223_220554"
    asyncio.run(production_loop(job_id))
