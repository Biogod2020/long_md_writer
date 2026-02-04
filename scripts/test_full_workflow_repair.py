import asyncio
import sys
import uuid
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.workflow_markdown import create_sota2_workflow
from src.core.types import AgentState, Manifest
from src.core.gemini_client import GeminiClient

RESUME_JOB_ID = "sota2_20260120_164630"
WORKSPACE_DIR = Path("workspace") / RESUME_JOB_ID
FIXED_THREAD_ID = f"test-repair-{uuid.uuid4().hex[:4]}"

async def test_full_repair_flow():
    print(f"🚀 Starting integration test for repair loop (Job: {RESUME_JOB_ID})")
    
    client = GeminiClient()
    app = create_sota2_workflow(client=client)
    config = {"configurable": {"thread_id": FIXED_THREAD_ID}}

    # Load existing manifest
    manifest_path = WORKSPACE_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
        manifest = Manifest(**manifest_data)

    # Initialize state at writer node
    state = AgentState(
        job_id=RESUME_JOB_ID,
        workspace_path=str(WORKSPACE_DIR),
        user_intent="Continue work",
        manifest=manifest,
        current_section_index=0,  # Start from first section to trigger fulfillment
        completed_md_sections=[],
        uar_path=str(WORKSPACE_DIR / "assets.json"),
        debug_mode=True
    )
    state.initialize_uar()
    
    # Force start at writer
    app.update_state(config, state.model_dump(), as_node="techspec")

    while True:
        try:
            print("\n" + "."*20 + " Workflow Running " + "."*20)
            last_state = None
            async for event in app.astream(None, config=config, stream_mode="values"):
                last_state = event

            state_info = app.get_state(config)
            if not state_info.next:
                print("\n✅ Workflow Finished.")
                break

            next_node = state_info.next[0]
            current_values = AgentState(**state_info.values)
            
            print(f"\n[INTERRUPT] Node: {next_node}")
            
            if next_node == "review_asset":
                print("\n" + "!"*20 + " ASSET FAILURE DETECTED " + "!"*20)
                print(f"Failed Asset: {current_values.failed_asset_id}")
                print("This is the blocking breakpoint we implemented.")
                choice = input("Enter 'retry' to re-run fulfillment or 'DONE' to skip: ").strip().lower()
                if choice == 'retry':
                    app.update_state(config, {"asset_revision_needed": False, "errors": []})
                else:
                    app.update_state(config, {"asset_revision_needed": False, "errors": []})
            
            elif next_node == "markdown_review":
                print(f"Reviewing Markdown for {len(current_values.completed_md_sections)} sections.")
                app.update_state(config, {"markdown_approved": True})
            
            elif next_node in ["review_brief", "review_outline"]:
                app.update_state(config, {"brief_approved": True, "outline_approved": True})
            
            else:
                print(f"Pausing at {next_node}. Press Enter to continue.")
                input()

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    asyncio.run(test_full_repair_flow())
