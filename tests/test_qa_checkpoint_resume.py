
import sys
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.types import AgentState
from src.orchestration.workflow_html import create_workflow
from src.core.gemini_client import GeminiClient

async def debug_qa_from_checkpoint():
    print("\n" + "="*60)
    print("🚦 LANGGRAPH CHECKPOINT RESUME TEST (MARKDOWN QA)")
    print("="*60)

    # 1. Load the checkpoint from disk
    checkpoint_path = Path("workspace/e2e_test_scratch/8bbdfd91/debug_logs/step_033.json")
    if not checkpoint_path.exists():
        print(f"❌ Error: Checkpoint not found at {checkpoint_path}")
        return

    print(f"📂 Loading state from: {checkpoint_path}")
    state_dict = json.loads(checkpoint_path.read_text())
    
    # --- Inject Full Raw Materials ---
    inputs_dir = root_dir / "inputs"
    exclude = ["prompt.txt", "slides_task_prompt.txt"]
    all_materials = []
    print("📚 Injecting additional raw materials from inputs/...")
    for f_path in sorted(inputs_dir.glob("*")):
        if f_path.is_file() and f_path.name not in exclude:
            print(f"   [+] Adding {f_path.name}")
            content = f_path.read_text(encoding="utf-8")
            all_materials.append(f"## Reference: {f_path.name}\n\n{content}")
    
    state_dict["raw_materials"] = (state_dict.get("raw_materials", "") + "\n\n" + "\n\n".join(all_materials)).strip()
    # ---------------------------------
    
    # LangGraph state needs to be a dict or AgentState instance
    # We'll use the dict but ensure it matches AgentState keys
    state_dict["skip_markdown_qa"] = False
    AgentState(**state_dict)

    # 2. Initialize Graph
    client = GeminiClient(timeout=300)
    app = create_workflow(client=client)

    # 3. Thread Configuration
    thread_id = "debug_resume_8bbdfd91"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"⚙️  Seeding LangGraph state into thread: {thread_id}")
    
    # We use update_state to "Time Travel" to this specific state.
    # By setting as_node="writer", we tell LangGraph that the 'writer' node just finished.
    # The graph will then look at the edges leaving 'writer' and move to 'markdown_qa'.
    app.update_state(config, state_dict, as_node="writer")

    print("🚀 Resuming graph execution (starting from Markdown QA)...")
    
    # We pass None as input because the state is already in the checkpointer
    async for event in app.astream(None, config, stream_mode="values"):
        # We look for which node is currently running
        # In 'values' mode, 'event' is the updated state
        pass 
    
    # Let's get the final state after the QA process
    final_state_snapshot = app.get_state(config)
    final_state = final_state_snapshot.values
    
    print("\n" + "-"*40)
    print("✅ TEST COMPLETE")
    print("-"*40)
    print(f"Current Node (from LangGraph Metadata): {final_state_snapshot.next}")
    print(f"Markdown Approved: {final_state.get('markdown_approved')}")
    print(f"QA Iterations: {final_state.get('md_qa_iterations')}")
    
    if final_state.get('markdown_approved'):
        print("🌟 Outcome: The QA agent reviewed the checkpointed content and APPROVED it.")
    else:
         print(f"🔍 Outcome: The QA agent has suggestions (Needs Revision: {final_state.get('md_qa_needs_revision')})")

if __name__ == "__main__":
    asyncio.run(debug_qa_from_checkpoint())
