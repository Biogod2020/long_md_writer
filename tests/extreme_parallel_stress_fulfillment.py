
import asyncio
import os
import shutil
from pathlib import Path
from src.core.types import AgentState, AssetSource
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient

async def stress_test_fulfillment():
    print("🚀 [STRESS TEST] Starting Extreme Parallel Fulfillment Test...")
    
    test_id = "stress_fulfillment_v1"
    workspace_path = Path("workspace") / test_id
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Prepare Dummy Markdown with multiple directives
    md_dir = workspace_path / "md"
    md_dir.mkdir()
    
    md_content = """# Stress Test Section
This is a test of the volume conductor theory.

:::visual {
  "id": "stress-fig-svg-1",
  "action": "GENERATE_SVG",
  "description": "A simple 2D diagram of a dipole vector P in a circular conductor."
}
:::

:::visual {
  "id": "stress-fig-web-1",
  "action": "SEARCH_WEB",
  "description": "A real clinical photograph of a 12-lead ECG machine sitting on a hospital cart."
}
:::

:::visual {
  "id": "stress-fig-svg-2",
  "action": "GENERATE_SVG",
  "description": "A circuit diagram showing three resistors R connected at a central point WCT."
}
:::
"""
    section_path = md_dir / "s1-test.md"
    section_path.write_text(md_content, encoding="utf-8")

    # 2. Setup State
    state = AgentState(
        job_id=test_id,
        workspace_path=str(workspace_path),
        completed_md_sections=[str(section_path)],
        debug_mode=True,
        uar_path=str(workspace_path / "assets.json")
    )
    state.initialize_uar()

    # 3. Run Fulfillment
    client = GeminiClient()
    agent = AssetFulfillmentAgent(client=client, max_concurrency=3)
    
    try:
        print("🛠️  Running parallel fulfillment...")
        await agent.run_parallel_async(state)
        print("✅ Parallel fulfillment execution completed.")
    except Exception as e:
        print(f"❌ CRITICAL FAILURE during fulfillment: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. Verification
    print("\n--- 🔍 Verification Report ---")
    
    # Check assets.json
    uar_file = workspace_path / "assets.json"
    if uar_file.exists():
        print(f"✅ assets.json exists. Size: {uar_file.stat().st_size} bytes")
    else:
        print("❌ assets.json is MISSING!")

    # Check for Caption Refinement in the MD file
    final_content = section_path.read_text(encoding="utf-8")
    if "<figcaption>" in final_content:
        print("✅ Figcaptions detected in final Markdown.")
        # Print a sample refined caption
        import re
        captions = re.findall(r'<figcaption>(.*?)</figcaption>', final_content)
        for i, cap in enumerate(captions):
            print(f"  Refined Caption {i+1}: {cap[:100]}...")
    else:
        print("❌ No figcaptions found in Markdown. Refinement might have failed.")

    # Check for physical files
    svgs = list((workspace_path / "agent_generated").glob("*.svg"))
    imgs = list((workspace_path / "assets" / "images").glob("*.jpg"))
    print(f"📊 Physical Stats: SVGs: {len(svgs)}, Sourced Images: {len(imgs)}")

    if len(svgs) >= 2 and len(imgs) >= 1 and "<figcaption>" in final_content:
        print("\n🏆 STRESS TEST PASSED SUCCESSFULLY.")
    else:
        print("\n💀 STRESS TEST FAILED (Partial Fulfillment).")

if __name__ == "__main__":
    asyncio.run(stress_test_fulfillment())
