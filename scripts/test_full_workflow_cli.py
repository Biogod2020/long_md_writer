"""
CLI Test Script for the Full Human-in-the-Loop Workflow.
Simulates human approval to run the pipeline non-interactively.
"""

import os
import uuid
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.orchestration.workflow_full import compile_full_workflow

def run_cli_test():
    # 1. Setup
    api_base_url = "http://localhost:7860"
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    workspace_root = Path("workspace_test")
    job_id = "test_ch2_" + str(uuid.uuid4())[:4]
    workspace_path = workspace_root / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "md").mkdir(exist_ok=True)
    (workspace_path / "html").mkdir(exist_ok=True)
    (workspace_path / "assets").mkdir(exist_ok=True)

    print(f"🚀 Starting Test: {job_id}")
    print(f"📂 Workspace: {workspace_path}")

    # 2. Prepare Materials
    inputs_dir = Path("inputs")
    materials = []
    
    # Style reference
    style_ref = (inputs_dir / "从偶极子到心电图.html").read_text(encoding="utf-8")
    materials.append(f"## STYLE REFERENCE (MIMIC THIS)\n{style_ref[:5000]}... (truncated)\n")
    
    # Knowledge sources
    for f in inputs_dir.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        materials.append(f"## SOURCE: {f.name}\n{content[:10000]}\n") # Truncate for speed
        
    user_goal = """
    写一个第二章——从电极到导联，解释不同的电极为什么可以“看”到心脏的不同位置。
    要求：
    - 模仿风格：参考‘从偶极子到心电图.html’的高端视觉风格。
    - 内容深度：从物理原理出发，解释导联轴和心脏电轴的关系。
    - 视觉效果：
        1. 必须包含内联 SVG 代码（如导联轴示意图）。
        2. 必须包含互联网来源的教学插图占位符（由 ImageSourcingAgent 处理）。
    - 语言：中文。
    """
    
    combined_materials = "\n\n".join(materials) + "\n\n# USER GOAL\n" + user_goal

    # 3. Initialize State
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    workflow_app = compile_full_workflow(client)
    thread_id = str(uuid.uuid4())[:8]
    print(f"🧶 Thread ID: {thread_id}")
    config = {"configurable": {"thread_id": thread_id}}

    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        raw_materials=combined_materials
    )

    # 4. Execution Loop (Handling Interrupts)
    print("\n--- Entering Graph Execution ---")
    
    def process_event(event):
        nonlocal state
        for node_name, node_state in event.items():
            if node_name == "__interrupt__":
                continue
            
            state = AgentState(**node_state)
            print(f"✅ Node Finished: {node_name}")
            if node_name == "writer":
                print(f"   [Writer] Sections done: {len(state.completed_md_sections)}")
            if node_name == "markdown_qa":
                print(f"   [MarkdownQA] Revision needed: {state.md_qa_needs_revision}")

    # Initial Run (stops at refiner)
    for event in workflow_app.stream(state.model_dump(), config=config):
        process_event(event)

    # LOOP: Check where we are and provide input
    while True:
        snapshot = workflow_app.get_state(config)
        next_nodes = snapshot.next
        
        if not next_nodes:
            print("\n🎉 Workflow Completed Successfully!")
            break
            
        target = next_nodes[0]
        print(f"\n⏸️ Interrupt before: {target}")
        
        # Auto-handle interrupts
        current_state_data = snapshot.values
        s = AgentState(**current_state_data)
        
        if target == "refiner":
            print("🤖 Simulating User Answers for Clarification...")
            mock_answers = {}
            for q in s.clarifier_questions:
                mock_answers[q['id']] = "Please follow the SOTA style guide and technical depth of the reference."
            s.clarifier_answers = mock_answers
            workflow_app.update_state(config, s.model_dump())
            
        elif target == "review_brief":
            print("🤖 Simulating User Approval: Project Brief")
            s.brief_approved = True
            workflow_app.update_state(config, s.model_dump())
            
        elif target == "review_outline":
            print("🤖 Simulating User Approval: Outline")
            s.outline_approved = True
            workflow_app.update_state(config, s.model_dump())
        
        else:
            print(f"🛑 Unexpected interrupt at {target}. Exiting.")
            break

        # Resume
        print(f"▶️ Resuming from {target}...")
        for event in workflow_app.stream(None, config=config):
            process_event(event)

    print("\n" + "="*40)
    print(f"Final Outcome: {state.final_html_path}")
    print("="*40)

if __name__ == "__main__":
    run_cli_test()
