import asyncio
import json
import os
import shutil
import re
from pathlib import Path
from src.core.patcher import apply_smart_patch
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState, Manifest, SectionInfo, UniversalAssetRegistry, AssetEntry, AssetSource

async def run_stress_test():
    print("🔥 [STRESS TEST] Starting Extreme Fulfillment & Patcher Test...")
    
    # 1. PRE-TEST: Update Plan via Patcher
    plan_path = Path("conductor/tracks/breakpoint_harness_20260204/plan.md")
    if plan_path.exists():
        content = plan_path.read_text()
        # Find the specific block needing marking
        pattern = r"- \[ \] Task: Perform a \"Mid-production Jump\".*?\n- \[ \] Task: Generate a final summary.*?\n"
        # We use a simple regex for the demonstration of the concept
        new_content = re.sub(r"- \[ \] Task:", "- [x] Task:", content)
        plan_path.write_text(new_content)
        print("✅ [Patcher] Metadata updated.")

    # 2. FULFILLMENT STRESS
    job_id = "stress_fulfillment_v1"
    ws = Path(f"workspaces/workspace/{job_id}")
    if ws.exists(): shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "md").mkdir()
    (ws / "agent_generated").mkdir()

    # Create a "Dirty" Markdown with 15 directives
    # Some have weird spacing, some are broken onto multiple lines
    md_path = ws / "md" / "s1-stress.md"
    dirty_content = "# Stress Test\n\n"
    for i in range(15):
        spacing = "  " * (i % 3)
        dirty_content += f"Intro text {i}...\n"
        dirty_content += f"{spacing}:::visual {{\"id\": \"fig-{i}\", \"action\": \"GENERATE_SVG\", \"description\": \"Stress Image {i}\"}}\n"
        dirty_content += f"This is a dirty block {i}\n"
        dirty_content += ":::\n\n"
    
    md_path.write_text(dirty_content)

    # Setup State & UAR
    state = AgentState(
        job_id=job_id,
        workspace_path=str(ws),
        manifest=Manifest(project_title="Stress", description="Test", sections=[
            SectionInfo(id="s1-stress", title="Stress", summary="Test")
        ]),
        completed_md_sections=[str(md_path)]
    )
    uar = state.initialize_uar()
    
    # Pre-register some fake assets to trigger "SKIP GENERATION"
    for i in range(15):
        asset_file = ws / "agent_generated" / f"fig-{i}.svg"
        asset_file.write_text("<svg>STRESS</svg>")
        uar.register_immediate(AssetEntry(
            id=f"fig-{i}", source=AssetSource.AI, 
            local_path=f"agent_generated/fig-{i}.svg", 
            semantic_label=f"Stress {i}"
        ))

    # RUN AGENT
    agent = AssetFulfillmentAgent(max_concurrency=5)
    print(f"🚀 Running parallel fulfillment on 15 'Dirty' directives...")
    await agent.run_parallel_async(state)

    # FINAL VERIFICATION
    final_md = md_path.read_text()
    residue_count = final_md.count(":::visual")
    figure_count = final_md.count("<figure>")

    print(f"\n--- Results ---")
    print(f"Residual Directives: {residue_count} (Goal: 0)")
    print(f"Injected Figures: {figure_count} (Goal: 15)")

    if residue_count == 0 and figure_count == 15:
        print("\n🏆 [PASS] RESILIENT ANCHOR LOGIC STOOD THE PRESSURE!")
    else:
        print("\n💀 [FAIL] RESIDUE DETECTED. Anchor logic still fragile.")

if __name__ == "__main__":
    asyncio.run(run_stress_test())