import argparse
import sys
import os
import asyncio
import uuid
import shutil
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.types import AgentState
from src.core.persistence import ProfileManager
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
    
    # Initialize Checkpointer (SQLite for persistent memory)
    db_path = workspace_path / "checkpoints.db"
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        
        # Setup workflow with interrupts
        interrupts = list(HIIP_GATES)
        if args.until:
            target_node = BP_TO_NODE.get(args.until)
            if target_node and target_node not in interrupts:
                interrupts.append(target_node)
        
        client = GeminiClient()
        app = create_sota2_workflow(client=client, checkpointer=checkpointer, interrupt_nodes=interrupts)
        config = {"configurable": {"thread_id": job_id}, "recursion_limit": 100}
        
        # --- Recovery Logic ---
        initial_input = None
        temp_state = AgentState(job_id=job_id, workspace_path=str(workspace_path))
        snm = SnapshotManager(temp_state)
        
        if args.list_history:
            print(f"\n📜 [HISTORY] Breakpoint History for {job_id}:")
            snapshots = snm.list_snapshots()
            for i, s in enumerate(snapshots):
                print(f"{i+1}. {s['id']} (Assets: {s['assets']}, Sections: {s['sections']})")
            return

        if args.jump:
            print(f"⏳ [TIME TRAVEL] Jumping back to snapshot: {args.jump}")
            snm.restore_artifacts(args.jump)
            state_obj = snm.load_snapshot_state(args.jump)
            await app.aupdate_state(config, state_obj.model_dump())
            print("✅ Logical and physical state synchronized.")

        current_state_info = await app.aget_state(config)
        
        if not current_state_info.values:
            print("🆕 FRESH START")
            user_intent = Path(args.input).read_text(encoding="utf-8") if args.input else "Technical guide on ECG dipole vector physics."
            reference_materials = Path(args.ref).read_text(encoding="utf-8") if args.ref else ""
            
            initial_input = AgentState(
                job_id=job_id,
                workspace_path=str(workspace_path),
                user_intent=user_intent,
                reference_materials=reference_materials,
                uar_path=str(workspace_path / "assets.json")
            )
        else:
            print(f"🔄 Resuming from SQLite checkpoint: {current_state_info.next or 'Completed'}")

        # --- Handle HITL Action (Initial Approval if provided) ---
        if current_state_info.next and not args.continuous:
            node = current_state_info.next[0]
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
                    approval_field = feedback_field.replace("user_", "").replace("_feedback", "") + "_approved"
                    await app.aupdate_state(config, {feedback_field: args.feedback, approval_field: False})

        # --- Execution Loop ---
        current_input = initial_input
        while True:
            last_state = None
            try:
                async for event in app.astream(current_input, config=config, stream_mode="values"):
                    last_state = event
                    current_input = None # Consume initial input
                
                final_state_info = await app.aget_state(config)
                if not final_state_info.next:
                    print("\n✅ PIPELINE COMPLETED.")
                    break
                
                reached_node = final_state_info.next[0]
                reached_bp = next((k for k, v in BP_TO_NODE.items() if v == reached_node), reached_node)
                print(f"\n🚩 [HALTED AT] {reached_bp} ({reached_node})")
                
                if args.continuous:
                    approval_field = {
                        "review_brief": "brief_approved",
                        "review_outline": "outline_approved",
                        "markdown_review": "markdown_approved",
                        "batch_asset_review": "asset_approved" # Placeholder for consistency
                    }.get(reached_node)
                    
                    if approval_field:
                        print(f"🤖 [AUTO-ADVANCE] Automatically approving {reached_node}...")
                        await app.aupdate_state(config, {approval_field: True})
                        current_input = None # Resume from checkpoint
                        continue 
                
                print(f"👉 To proceed: run with --job-id {job_id} [--approve | --feedback \"...\"]")
                break
                    
            except Exception as e:
                print(f"❌ Pipeline Error: {e}")
                import traceback; traceback.print_exc()
                break

def main():
    parser = argparse.ArgumentParser(description="SOTA 2.0 Native Breakpoint Harness (Snapshot-Based)")
    parser.add_argument("--until", choices=VALID_BREAKPOINTS, help="Stop at BP-N")
    parser.add_argument("--job-id", help="Resume existing job via snapshots")
    parser.add_argument("--input", help="Prompt file")
    parser.add_argument("--ref", help="Reference materials file")
    parser.add_argument("--approve", action="store_true", help="Approve HITL gate")
    parser.add_argument("--feedback", help="Inject feedback to HITL gate")
    parser.add_argument("--list-history", action="store_true", help="List all snapshots for this job")
    parser.add_argument("--jump", help="Jump back to a specific snapshot ID")
    parser.add_argument("--continuous", action="store_true", help="Auto-approve gates and run to the end")
    
    args = parser.parse_args()
    asyncio.run(run_flow(args))

if __name__ == "__main__":
    main()
