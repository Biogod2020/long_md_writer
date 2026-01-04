import os
import uuid
import json
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState
from src.agents.clarifier_agent import ClarifierAgent
from src.agents.refiner_agent import RefinerAgent
from src.agents.outline_agent import OutlineAgent
from src.agents.techspec_agent import TechSpecAgent
from src.orchestration.workflow import create_generation_workflow

def run_production_test():
    # 1. Configuration
    api_base_url = "http://localhost:7860"
    auth_token = os.getenv("GEMINI_AUTH_PASSWORD", "123456")
    workspace_base = Path("workspace")
    job_id = "sota_prod_" + str(uuid.uuid4())[:4]
    workspace_path = workspace_base / job_id
    
    print(f"Starting SOTA Production Test: {job_id}")
    print(f"Workspace: {workspace_path}")
    
    # 2. Read Input Materials from @[inputs]
    inputs_dir = Path("inputs")
    raw_materials_parts = []
    for f in inputs_dir.glob("*.md"):
        print(f"Adding source: {f.name}")
        content = f.read_text(encoding="utf-8")
        raw_materials_parts.append(f"## SOURCE FILE: {f.name}\n\n{content}")
    
    combined_materials = "\n\n" + "="*40 + "\n\n".join(raw_materials_parts)
    
    # 3. User Goal
    user_goal = """
    Create a SOTA-level, comprehensive digital textbook lecture on 'Advanced Cardiovascular Electrophysiology: From Dipoles to Clinical ECG'.
    
    TARGET WORD COUNT: Approximately 5000 words.
    NARRATIVE STYLE: Graduate-level technical depth, starting from first-principles biophysics.
    VISUAL STYLE: 'SOTA High-Tech Dark' (Glassmorphism, Neon Cyan accents, high-end typography).
    INTERACTIVITY: Use interactive SVG placeholders for cardiac dipole animations and ECG wave derivations.
    """
    
    # 4. Initialize State
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        raw_materials=combined_materials + "\n\n# USER GOAL\n" + user_goal
    )
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "md").mkdir(exist_ok=True)
    (workspace_path / "html").mkdir(exist_ok=True)
    (workspace_path / "assets").mkdir(exist_ok=True)
    
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    # Check connection
    if not client.test_connection():
        print("Error: Cannot connect to Gemini API proxy at http://localhost:7860")
        return

    # 5. Step 0: Clarifier Stage
    print("\n--- [Step 0] Clarifying Requirements ---")
    clarifier = ClarifierAgent(client)
    questions = clarifier.run(state)
    print(f"Clarifier generated {len(questions)} questions.")
    
    # Auto-answer for testing purposes
    simulated_answers = {}
    for q in questions:
        print(f"  ? {q['question']}")
        if "audience" in q['category'].lower():
            ans = "Medical students and biomedical engineers. Keep the rigor high."
        elif "visual" in q['category'].lower() or "style" in q['category'].lower():
            ans = "Deep indigo background, electric cyan vectors, animated gradient descent style paths."
        elif "depth" in q['category'].lower():
            ans = "Derive everything from the Poisson equation and Ohm's law where relevant."
        else:
            ans = "Follow SOTA best practices for high-end technical documentation."
        simulated_answers[q['id']] = ans
    
    # 6. Step 1: Refiner Stage
    print("\n--- [Step 1] Synthesizing Project Brief ---")
    refiner = RefinerAgent(client)
    brief = refiner.run(state, clarification_answers=simulated_answers)
    state.project_brief = brief
    print("Project Brief generated successfully.")
    
    # 7. Step 2.1: Outline Stage
    print("\n--- [Step 2.1] Designing Document Outline ---")
    outline_agent = OutlineAgent(client)
    state = outline_agent.run(state)
    if state.errors:
        print(f"Outline Errors: {state.errors}")
        return
    print(f"Outline created: {state.manifest.project_title}")
    print(f"Sections: {[s.title for s in state.manifest.sections]}")
    
    # 8. Step 2.2: TechSpec Stage
    print("\n--- [Step 2.2] Generating Technical Specification (SOTA Description) ---")
    ts_agent = TechSpecAgent(client)
    state = ts_agent.run(state)
    if state.errors:
        print(f"TechSpec Errors: {state.errors}")
        return
    print(f"SOTA Description generated ({len(state.manifest.description)} characters).")
    
    # 9. Step 3: Production Pipeline
    print("\n--- [Step 3] Launching Production Pipeline ---")
    print("Note: This involves multi-agent writing, designing (CSS/JS), transforming, and SVG creation.")
    workflow = create_generation_workflow(client)
    app = workflow.compile()
    
    # Run the compiled LangGraph workflow
    result = app.invoke(state.model_dump())
    final_state = AgentState(**result)
    
    if final_state.errors:
        print(f"\nPRODUCTION FAILED with {len(final_state.errors)} errors:")
        for err in final_state.errors:
            print(f"  - {err}")
    else:
        print("\n" + "="*40)
        print("SOTA PRODUCTION SUCCESSFUL!")
        print(f"Final HTML: {final_state.final_html_path}")
        print(f"Assets Directory: {Path(final_state.workspace_path) / 'assets'}")
        print("="*40)

if __name__ == "__main__":
    run_production_test()
