import asyncio
from pathlib import Path
from src.orchestration.workflow_markdown import create_sota2_workflow
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def resume_task(job_id: str):
    workspace_path = Path(f"workspace/{job_id}")
    db_path = workspace_path / "checkpoints.db"
    
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        client = GeminiClient()
        app = create_sota2_workflow(client=client, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": job_id}}
        
        # 1. Update State to APPROVED (Outline Phase)
        print(f"✅ Approving Outline for {job_id}...")
        await app.aupdate_state(config, {"outline_approved": True})
        
        # 2. Resume execution
        print(f"🚀 Resuming workflow to TechSpec and Writing...")
        async for event in app.astream(None, config=config, stream_mode="values"):
            # Progress indicators
            if isinstance(event, dict):
                idx = event.get("current_section_index", 0)
                if idx > 0:
                    print(f"  [Progress] Section {idx} written.")
            
        # Check next interrupt
        state_info = await app.aget_state(config)
        if state_info.next:
            print(f"\n⏸️ Workflow paused at: {state_info.next[0]}")
        else:
            print("\n🏁 Workflow completed successfully!")

if __name__ == "__main__":
    import sys
    job_id = "sota2_20260223_220554"
    asyncio.run(resume_task(job_id))
