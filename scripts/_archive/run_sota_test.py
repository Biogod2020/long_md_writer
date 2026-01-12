import os
import uuid
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.agents.clarifier_agent import ClarifierAgent
from src.agents.refiner_agent import RefinerAgent
from src.agents.outline_agent import OutlineAgent
from src.agents.techspec_agent import TechSpecAgent
from src.orchestration.workflow import create_generation_workflow

def run_sota_flow():
    # 1. Configuration
    api_base_url = "http://localhost:7860"
    auth_token = "123456" 
    workspace_base = Path("workspace")
    job_id = "ml_test_" + str(uuid.uuid4())[:4]
    workspace_path = workspace_base / job_id
    
    # Non-medical topic for verification
    user_prompt = "I want to create a SOTA interactive lecture about 'The First-Principles of Machine Learning'. Specifically, I want to explain Gradient Descent and Backpropagation by deriving them from basic multivariable calculus. The audience is first-year CS students. Use a high-tech dark theme with interactive SVG gradients to show the loss landscape."
    
    # 2. Preparation
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        raw_materials=user_prompt
    )
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "md").mkdir(exist_ok=True)
    (workspace_path / "html").mkdir(exist_ok=True)
    (workspace_path / "assets").mkdir(exist_ok=True)
    
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    # 3. Clarifier Stage
    print(f"[{job_id}] Step 0: Clarifying Needs...")
    clarifier = ClarifierAgent(client)
    questions = clarifier.run(state)
    print(f"Clarifier asked {len(questions)} questions:")
    for q in questions:
        print(f"  - [{q['id']}] {q['question']}")
    
    # Simulate answers
    simulated_answers = {
        q['id']: f"Simulated answer for {q['category']}: Focus on visual intuition first, then formal proof." 
        for q in questions
    }
    print("Simulated answers provided.")
    
    # 4. Refiner Stage
    print(f"[{job_id}] Step 1: Refining Project Brief...")
    refiner = RefinerAgent(client)
    brief = refiner.run(state, clarification_answers=simulated_answers)
    state.project_brief = brief
    print("Brief generated successfully.")
    
    # 5. Outline Stage
    print(f"[{job_id}] Step 2.1: Designing Outline...")
    outline_agent = OutlineAgent(client)
    state = outline_agent.run(state)
    if state.errors:
        print(f"Outline Errors: {state.errors}")
        return
    print(f"Outline created: {state.manifest.project_title}")
    
    # 6. TechSpec Stage
    print(f"[{job_id}] Step 2.2: Generating Technical Spec (SOTA Description)...")
    ts_agent = TechSpecAgent(client)
    state = ts_agent.run(state)
    if state.errors:
        print(f"TechSpec Errors: {state.errors}")
        return
    print(f"SOTA Description generated ({len(state.manifest.description)} chars).")
    
    # 7. Production Stage
    print(f"[{job_id}] Step 3: Production Pipeline...")
    workflow = create_generation_workflow(client)
    app = workflow.compile()
    
    result = app.invoke(state.model_dump())
    final_state = AgentState(**result)
    
    if final_state.errors:
        print(f"Workflow Errors: {final_state.errors}")
    else:
        print(f"Success! Final HTML: {final_state.final_html_path}")
        print(f"Workspace: {final_state.workspace_path}")

if __name__ == "__main__":
    run_sota_flow()
