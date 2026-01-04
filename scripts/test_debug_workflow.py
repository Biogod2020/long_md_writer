"""
Debug CLI Test Script - Full Workflow with Detailed Logging
Preserves all intermediate artifacts for analysis.
"""

import os
import uuid
import json
import traceback
from pathlib import Path
from datetime import datetime
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.orchestration.workflow_full import compile_full_workflow

def run_debug_test():
    # 1. Setup
    api_base_url = "http://localhost:7860"
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    workspace_root = Path("workspace_debug")
    job_id = "debug_" + datetime.now().strftime("%H%M%S")
    workspace_path = workspace_root / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "md").mkdir(exist_ok=True)
    (workspace_path / "html").mkdir(exist_ok=True)
    (workspace_path / "assets").mkdir(exist_ok=True)
    (workspace_path / "assets" / "images").mkdir(exist_ok=True)
    
    log_file = workspace_path / "debug_log.txt"

    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log(f"🚀 Starting Debug Test: {job_id}")
    log(f"📂 Workspace: {workspace_path}")

    # 2. Prepare Materials
    inputs_dir = Path("inputs")
    materials = []
    
    # Style reference
    style_ref = (inputs_dir / "从偶极子到心电图.html").read_text(encoding="utf-8")
    materials.append(f"## STYLE REFERENCE (MIMIC THIS)\n{style_ref[:8000]}... (truncated)\n")
    
    # Knowledge sources
    for f in inputs_dir.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        materials.append(f"## SOURCE: {f.name}\n{content[:15000]}\n")
        
    user_goal = """
    写一个第二章——从电极到导联，解释不同的电极为什么可以"看"到心脏的不同位置。
    要求：
    - 模仿风格：参考'从偶极子到心电图.html'的高端视觉风格。
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
    log(f"🧶 Thread ID: {thread_id}")
    config = {"configurable": {"thread_id": thread_id}}

    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        raw_materials=combined_materials
    )

    # 4. Execution Loop (Handling Interrupts)
    log("\n--- Entering Graph Execution ---")
    
    def process_event(event):
        nonlocal state
        for node_name, node_state in event.items():
            if node_name == "__interrupt__":
                continue
            
            state = AgentState(**node_state)
            log(f"✅ Node Finished: {node_name}")
            
            # Detailed logging per node
            if node_name == "clarifier":
                log(f"   Questions: {len(state.clarifier_questions)}")
            elif node_name == "refiner":
                log(f"   Brief length: {len(state.project_brief or '')} chars")
            elif node_name == "outline":
                log(f"   Sections: {len(state.manifest.sections) if state.manifest else 0}")
            elif node_name == "writer":
                log(f"   MD sections: {len(state.completed_md_sections)}")
            elif node_name == "markdown_qa":
                log(f"   Revision needed: {state.md_qa_needs_revision}")
            elif node_name == "design":
                log(f"   CSS: {state.css_path}, JS: {state.js_path}")
            elif node_name == "transformer":
                log(f"   HTML sections: {len(state.completed_html_sections)}")
            elif node_name == "image_sourcer":
                log(f"   Completed HTML: {state.completed_html_sections}")
            elif node_name == "assembler":
                log(f"   Final HTML: {state.final_html_path}")
            elif node_name == "visual_qa":
                log(f"   VQA needs reassembly: {state.vqa_needs_reassembly}")
            
            # Log errors
            if state.errors:
                log(f"   ⚠️ ERRORS: {state.errors}")

    try:
        # Initial Run (stops at refiner)
        for event in workflow_app.stream(state.model_dump(), config=config):
            process_event(event)

        # LOOP: Check where we are and provide input
        while True:
            snapshot = workflow_app.get_state(config)
            next_nodes = snapshot.next
            
            if not next_nodes:
                log("\n🎉 Workflow Completed Successfully!")
                break
                
            target = next_nodes[0]
            log(f"\n⏸️ Interrupt before: {target}")
            
            # Auto-handle interrupts
            current_state_data = snapshot.values
            s = AgentState(**current_state_data)
            
            if target == "refiner":
                log("🤖 Simulating User Answers for Clarification...")
                mock_answers = {}
                for q in s.clarifier_questions:
                    mock_answers[q['id']] = "请遵循参考文档的 SOTA 视觉风格和技术深度。包含足够的内联 SVG 和图片占位符。"
                s.clarifier_answers = mock_answers
                workflow_app.update_state(config, s.model_dump())
                
            elif target == "review_brief":
                log("🤖 Simulating User Approval: Project Brief")
                s.brief_approved = True
                workflow_app.update_state(config, s.model_dump())
                
            elif target == "review_outline":
                log("🤖 Simulating User Approval: Outline")
                s.outline_approved = True
                workflow_app.update_state(config, s.model_dump())
            
            else:
                log(f"🛑 Unexpected interrupt at {target}. Exiting.")
                break

            # Resume
            log(f"▶️ Resuming from {target}...")
            for event in workflow_app.stream(None, config=config):
                process_event(event)

    except Exception as e:
        log(f"🔥 EXCEPTION: {e}")
        log(traceback.format_exc())

    # 5. Save final state
    final_state_path = workspace_path / "final_state.json"
    with open(final_state_path, "w", encoding="utf-8") as f:
        json.dump(state.model_dump(), f, indent=2, ensure_ascii=False, default=str)
    
    log("\n" + "="*50)
    log(f"Final HTML: {state.final_html_path}")
    log(f"Errors: {state.errors}")
    log(f"MD Sections: {len(state.completed_md_sections)}")
    log(f"HTML Sections: {len(state.completed_html_sections)}")
    log(f"Debug Log: {log_file}")
    log("="*50)

if __name__ == "__main__":
    run_debug_test()
