import argparse
import sys
import os
import asyncio
import uuid
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.types import AgentState
from src.core.persistence import ProfileManager, reload_profile_to_state
from src.core.gemini_client import GeminiClient
from src.orchestration.workflow_markdown import create_sota2_workflow
from src.orchestration.breakpoint_manager import SnapshotManager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Valid Breakpoint IDs based on SOTA 2.0 specs
VALID_BREAKPOINTS = [
    "BP-1", "BP-2", "BP-3", "BP-4", "BP-5", 
    "BP-6", "BP-7", "BP-8", "BP-9", "BP-10"
]

# SOTA Mapping: Breakpoints -> LangGraph Nodes
BP_TO_NODE = {
    "BP-1": "asset_indexer",
    "BP-2": "refiner",
    "BP-3": "architect",
    "BP-4": "techspec",
    "BP-5": "writer",
    "BP-6": "markdown_qa",
    "BP-8": "batch_fulfillment",
    "BP-10": "editorial_qa"
}

# Critical HIIP Gates
HIIP_GATES = ["review_brief", "review_outline", "markdown_review", "batch_asset_review"]

async def run_flow(args):
    print(f"🚀 SOTA 2.0 Breakpoint Test Harness (Thread: {args.job_id or 'new'})")
    
    job_id = args.job_id if args.job_id else f"audit_{uuid.uuid4().hex[:6]}"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    db_path = workspace_path / "checkpoints.db"
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        
        interrupts = list(HIIP_GATES)
        if args.until:
            target_node = BP_TO_NODE.get(args.until)
            if target_node and target_node not in interrupts:
                interrupts.append(target_node)
        
        client = GeminiClient()
        app = create_sota2_workflow(client=client, checkpointer=checkpointer, interrupt_nodes=interrupts)
        config = {"configurable": {"thread_id": job_id}, "recursion_limit": 50}
        
        current_state_info = await app.aget_state(config)
        
        # --- Handle User Intervention (Approve or Feedback) ---
        if current_state_info.next:
            node = current_state_info.next[0]
            print(f"⏸️ Paused at: {node}")
            
            if args.approve:
                print(f"✅ ACTION: Approve {node}")
                approval_field = {
                    "review_brief": "brief_approved",
                    "review_outline": "outline_approved",
                    "markdown_review": "markdown_approved"
                }.get(node)
                if approval_field:
                    await app.aupdate_state(config, {approval_field: True})
            
            elif args.feedback:
                print(f"🛠️ ACTION: Inject Feedback to {node}")
                feedback_field = {
                    "review_brief": "user_brief_feedback",
                    "review_outline": "user_outline_feedback",
                    "markdown_review": "user_markdown_feedback"
                }.get(node)
                if feedback_field:
                    # Injecting feedback and ENSURING approved is False
                    approval_field = feedback_field.replace("user_", "").replace("_feedback", "") + "_approved"
                    await app.aupdate_state(config, {feedback_field: args.feedback, approval_field: False})
            
            initial_input = None 
        else:
            print("🆕 FRESH START")
            initial_input = AgentState(
                job_id=job_id,
                workspace_path=str(workspace_path),
                user_intent=Path(args.input).read_text(encoding="utf-8") if args.input else "Technical guide on ECG dipole vector physics.",
                uar_path=str(workspace_path / "assets.json")
            )

        # --- Execution ---
        last_state = None
        async for event in app.astream(initial_input, config=config, stream_mode="values"):
            last_state = event
            
        # --- Post-Run Report ---
        final_state_info = await app.aget_state(config)
        if final_state_info.next:
            reached_node = final_state_info.next[0]
            reached_bp = next((k for k, v in BP_TO_NODE.items() if v == reached_node), reached_node)
            
            print(f"\n🚩 [GATE REACHED] {reached_bp}")
            
            state_obj = last_state if isinstance(last_state, AgentState) else AgentState(**last_state)
            snm = SnapshotManager(state_obj)
            snm.capture(reached_bp, auto_continue=True)
            print(f"👉 To proceed: run with --job-id {job_id} [--approve | --feedback \"...\"]")
        else:
            print("\n✅ PIPELINE COMPLETED.")

def main():
    parser = argparse.ArgumentParser(description="SOTA 2.0 Native Breakpoint Harness")
    parser.add_argument("--until", choices=VALID_BREAKPOINTS, help="Stop at BP-N")
    parser.add_argument("--job-id", help="Resume existing thread")
    parser.add_argument("--input", help="Prompt file")
    parser.add_argument("--approve", action="store_true", help="Approve HITL gate")
    parser.add_argument("--feedback", help="Inject feedback to HITL gate")
    
    args = parser.parse_args()
    asyncio.run(run_flow(args))

if __name__ == "__main__":
    main()
