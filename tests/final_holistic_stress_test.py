import asyncio
import json
import shutil
import os
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient

async def run_holistic_stress():
    print("🧪 [FINAL STRESS] Starting Holistic SOTA 2.0 Production Test...")
    
    job_id = "final_holistic_v1"
    ws = Path(f"workspaces/workspace/{job_id}")
    if ws.exists(): shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "md").mkdir()
    (ws / "agent_generated").mkdir()
    (ws / "agent_sourced").mkdir()

    md_content = """# Holistic Stress Test Report

## Section 1: Anatomy & Electrophysiology
:::visual {"id": "st-fig-purkinje-net", "action": "GENERATE_SVG", "description": "A detailed 3D-like anatomical diagram of the human heart with the Purkinje fiber network highlighted in glowing yellow. Show the bundle of His, left and right bundle branches. Labels must not overlap and should be legible against the heart muscle."}
The electrical conduction system is the heart's wiring...

:::visual {"id": "st-fig-electrode-photo", "action": "SEARCH_WEB", "description": "High-quality medical photo showing standard 10-electrode placement on a human torso for a 12-lead ECG. Clear view of V1-V6 positions."}
Proper electrode placement is critical for accurate diagnosis.

## Section 2: Hemodynamics
:::visual {"id": "st-fig-wiggers-diagram", "action": "GENERATE_SVG", "description": "A complete Wiggers diagram showing synchronized Left Ventricular Pressure, Aortic Pressure, Atrial Pressure, and Left Ventricular Volume over one cardiac cycle. Include an ECG strip at the bottom aligned with the phases. Use a clean, clinical grid and distinct colors for each curve."}
Understanding the relationship between electrical and mechanical events...

## Section 3: Diagnostic Logic
:::visual {"id": "st-flow-stemi-algorithm", "action": "GENERATE_MERMAID", "description": "A professional clinical flowchart for STEMI (ST-Elevation Myocardial Infarction) diagnosis. Starting from Chest Pain, moving through ECG acquisition, identifying ST elevation in 2+ contiguous leads, and deciding between PCI or Thrombolysis based on time to cath lab (90 mins)."}
Time is muscle in the management of acute coronary syndromes.

## Section 4: Complex Vectors
:::visual {"id": "st-fig-hexaxial-3d", "action": "GENERATE_SVG", "description": "A sophisticated representation of the Frontal Hexaxial system (I, II, III, aVR, aVL, aVF) superimposed on a semi-transparent torso. Show the angles clearly: I at 0, aVF at +90, etc. Use a gradient wheel and ensure all text labels are perfectly balanced."}
The hexaxial system provides a 360-degree view of the heart's frontal electrical activity.

:::visual {"id": "st-fig-ecg-report-sample", "action": "SEARCH_WEB", "description": "A standard clinical 12-lead ECG report printout showing normal sinus rhythm. Clear 12-lead grid with lead labels (I, II, III, aVR, etc.)."}
The final output is the 12-lead report.
"""
    md_path = ws / "md" / "holistic_report.md"
    md_path.write_text(md_content)

    state = AgentState(
        job_id=job_id,
        workspace_path=str(ws),
        manifest=Manifest(project_title="Holistic Stress", description="Full Test", sections=[
            SectionInfo(id="holistic_report", title="Holistic Stress", summary="Final Validation")
        ]),
        completed_md_sections=[str(md_path)]
    )
    
    agent = AssetFulfillmentAgent(client=GeminiClient(), debug=True, max_concurrency=3)
    
    print("\n🚀 Launching Parallel Fulfillment for all 6 assets...")
    await agent.run_parallel_async(state)
    
    # 最终盘点
    final_md = md_path.read_text()
    residue = final_md.count(":::visual")
    figure_count = final_md.count("<figure>")
    mermaid_count = final_md.count("mermaid")
    
    with open(ws / "assets.json", "r") as f:
        uar_data = json.load(f)
    
    print("\n--- FINAL RESULTS ---")
    print(f"Residual Directives: {residue}")
    print(f"Injected Figures: {figure_count}")
    print(f"Injected Mermaid: {mermaid_count}")
    print(f"Assets in UAR: {len(uar_data['assets'])}")
    
    if residue == 0 and figure_count >= 3:
        print("\n🏆 [PASS] SOTA 2.0 passed the holistic stress test!")
    else:
        print("\n💀 [FAILURE] Residue detected.")

if __name__ == "__main__":
    asyncio.run(run_holistic_stress())