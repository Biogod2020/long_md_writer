import asyncio
import sys
import random
from pathlib import Path
from typing import List

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.gemini_client import GeminiClient
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.agents.asset_management.models import VisualDirective
from src.core.types import AgentState, AssetEntry

async def run_sourcing_stress_test():
    print("🚀 [STRESS TEST] Starting Real Web Sourcing Concurrency Test...")
    print("🎯 Goal: Verify that search_semaphore prevents Google Captcha under load.")
    
    # 1. Setup Environment
    client = GeminiClient()
    # High concurrency fulfillment but throttled search
    fulfillment = AssetFulfillmentAgent(client=client, debug=True, max_concurrency=5)
    
    test_ws = Path("workspace/stress_sourcing")
    if test_ws.exists():
        import shutil
        shutil.rmtree(test_ws)
    test_ws.mkdir(parents=True)
    
    state = AgentState(job_id="stress_sourcing", workspace_path=str(test_ws))
    
    # 2. Define 5 Parallel Search Directives
    intents = [
        "Einthoven triangle classical physics diagram",
        "Willem Einthoven historical portrait 1920s",
        "Modern 12-lead ECG machine electrodes on patient",
        "Galvanometer antique medical instrument photo",
        "Augustus Waller capillary electrometer experiment"
    ]
    
    directives = []
    for i, intent in enumerate(intents):
        directives.append(VisualDirective(
            id=f"s1-fig-stress-{i+1}",
            description=intent,
            raw_block=f":::visual stress {i+1}:::",
            start_pos=0,
            end_pos=0
        ))

    # 3. Launch Parallel Tasks
    print(f"\n🔥 Launching {len(directives)} parallel search tasks (Fulfillment concurrency: 5)...")
    
    async def task_wrapper(d):
        ns = "s1"
        trace = {"id": d.id, "steps": []}
        src_path = test_ws / "agent_sourced"
        src_path.mkdir(exist_ok=True)
        
        # Use the real fulfillment internal method which has the semaphore
        result_d, asset = await fulfillment._fulfill_search_step(
            d, state.get_uar(), src_path, ns, state, trace
        )
        return (d.id, result_d.fulfilled, asset is not None)

    start_time = asyncio.get_event_loop().time()
    results = await asyncio.gather(*(task_wrapper(d) for d in directives))
    end_time = asyncio.get_event_loop().time()

    # 4. Reporting
    print("\n" + "="*50)
    print("📊 STRESS TEST RESULTS")
    print("="*50)
    success_count = sum(1 for r in results if r[2])
    for r in results:
        status = "✅ SUCCESS" if r[2] else "❌ FAILED"
        print(f"  - {r[0]}: {status}")
    
    print(f"\n⏱️ Total Time: {end_time - start_time:.2f}s")
    print(f"📈 Success Rate: {success_count}/{len(intents)}")
    
    if success_count == len(intents):
        print("\n🏆 SUCCESS: Throttled search strategy successfully bypassed Captchas!")
    else:
        print("\n⚠️ WARNING: Some searches failed. Check logs for '[!] Google Captcha' markers.")

if __name__ == "__main__":
    asyncio.run(run_sourcing_stress_test())
