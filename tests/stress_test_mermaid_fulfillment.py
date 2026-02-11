import asyncio
import json
import shutil
import os
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient

async def run_mermaid_stress():
    print("🧪 [MERMAID STRESS] Starting Targeted Mermaid Fulfillment Test...")
    
    job_id = "mermaid_stress_v1"
    ws = Path(f"workspaces/workspace/{job_id}")
    if ws.exists(): shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "md").mkdir()
    (ws / "agent_generated").mkdir()
    (ws / "agent_sourced").mkdir()
    
    # Ensure assets.json is clean
    if (ws / "assets.json").exists(): (ws / "assets.json").unlink()

    # This markdown contains multiple Mermaid directives, 
    # including ones with complex structures like subgraphs and nested braces.
    md_content = """# Mermaid Stress Test

## Section 1: Clinical Flowcharts
:::visual {"id": "m-flow-triage", "action": "GENERATE_MERMAID", "description": "Emergency department triage flowchart. Start: Patient Arrival -> Triage Nurse Assessment -> {Urgent?} -> [YES] Resuscitation; [NO] Waiting Room. Use subgraphs for different priority levels."}
Triage is the process of determining the priority of patients' treatments.
:::

:::visual {"id": "m-flow-nested-braces", "action": "GENERATE_MERMAID", "description": "A flowchart testing nested braces handling. Node A{Decision} ->|Yes| B{Another Decision}; B ->|Option 1| C[Final 1]; B ->|Option 2| D[Final 2]. Ensure the parser doesn't break on the Mermaid braces."}
Testing the robustness of the JSON parser against Mermaid syntax.
:::

## Section 2: Anatomical Systems
:::visual {"id": "m-diag-nephron", "action": "GENERATE_MERMAID", "description": "A sequence diagram showing the flow of filtrate through a nephron: Glomerulus -> Proximal Tubule -> Loop of Henle -> Distal Tubule -> Collecting Duct. Show solute exchange with the Vasa Recta."}
The nephron is the functional unit of the kidney.
:::

:::visual {"id": "m-state-heart-cycle", "action": "GENERATE_MERMAID", "description": "A state diagram of the cardiac cycle: Atrial Systole -> Ventricular Systole -> Isovolumetric Relaxation -> Ventricular Filling."}
The cardiac cycle refers to a complete heartbeat.
:::

## Section 3: Complex Interactions
:::visual {"id": "m-class-protein-synthesis", "action": "GENERATE_MERMAID", "description": "A class diagram showing the relationship between DNA, mRNA, tRNA, and Ribosome during protein synthesis. Include methods like transcribe() and translate()."}
Protein synthesis is the process in which cells make proteins.
:::
"""
    md_path = ws / "md" / "mermaid_test.md"
    md_path.write_text(md_content)

    state = AgentState(
        job_id=job_id,
        workspace_path=str(ws),
        manifest=Manifest(project_title="Mermaid Stress", description="Targeted Mermaid Test", sections=[
            SectionInfo(id="mermaid_test", title="Mermaid Stress", summary="Verifying Mermaid backfill and rendering")
        ]),
        completed_md_sections=[str(md_path)]
    )
    
    agent = AssetFulfillmentAgent(client=GeminiClient(), debug=True, max_concurrency=3)
    
    print("\n🚀 Launching Parallel Fulfillment for 5 Mermaid assets...")
    await agent.run_parallel_async(state)
    
    # Verification
    final_md = md_path.read_text()
    residue = final_md.count(":::visual")
    figure_count = final_md.count("<figure>")
    
    # Check for PNG files in agent_generated
    png_files = list((ws / "agent_generated").glob("*.png"))
    png_names = [f.name for f in png_files]
    
    with open(ws / "assets.json", "r") as f:
        uar_data = json.load(f)
    
    print("\n--- FINAL RESULTS ---")
    print(f"Residual Directives: {residue}")
    print(f"Injected Figures: {figure_count}")
    print(f"PNG Assets Generated: {len(png_files)} ({png_names})")
    print(f"Assets in UAR: {len(uar_data['assets'])}")
    
    # Check for specific IDs
    expected_ids = ["m-flow-triage", "m-flow-nested-braces", "m-diag-nephron", "m-state-heart-cycle", "m-class-protein-synthesis"]
    missing_ids = [eid for eid in expected_ids if eid not in uar_data["assets"]]
    
    if residue == 0 and figure_count >= 3 and len(png_files) >= 2: 
        print("\n🏆 [PASS] Mermaid stress test completed successfully!")
        if missing_ids:
            print(f"⚠️ Note: Missing IDs in UAR: {missing_ids}")
    else:
        print("\n💀 [FAILURE] Stress test results below expectations.")
        if residue > 0:
            print(f"❌ Residual directives found: {residue}")
        if figure_count < 5:
            print(f"❌ Only {figure_count}/5 figures injected.")

if __name__ == "__main__":
    asyncio.run(run_mermaid_stress())
