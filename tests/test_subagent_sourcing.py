import asyncio
import os
import shutil
import time
from pathlib import Path
from src.agents.image_sourcing.agent import ImageSourcingAgent
from src.agents.asset_management.models import VisualDirective
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, SectionInfo

async def run_subagent_test():
    print("🚀 [SUB-AGENT TEST] Testing the new fulfill_directive_async interface...")
    
    client = GeminiClient()
    agent = ImageSourcingAgent(client=client, debug=True, headless=True)
    
    ws_id = f"test_subagent_{int(time.time())}"
    ws_path = Path(f"workspaces/workspace/{ws_id}")
    ws_path.mkdir(parents=True, exist_ok=True)
    
    state = AgentState(
        job_id=ws_id,
        workspace_path=str(ws_path),
        manifest=Manifest(project_title="SubAgent Test", description="Neutral Benchmark", sections=[
            SectionInfo(id="sec-1", title="Test", summary="Testing subagent logic")
        ])
    )
    
    # 补齐 VisualDirective 的必填字段
    directives = [
        VisualDirective(id="gz2hs-logo", description="广州市第二中学的官方校徽，带有红色圆形的元字图案", raw_block="mock", start_pos=0, end_pos=0),
        VisualDirective(id="gz2hs-uniform", description="广州市第二中学的校服，包括日常穿着的运动服款式", raw_block="mock", start_pos=0, end_pos=0),
        VisualDirective(id="person-yujintai", description="复旦大学研究员郁金泰在学术场合的照片", raw_block="mock", start_pos=0, end_pos=0),
        VisualDirective(id="fig-transformer", description="Transformer 论文中的 Figure 1 模型架构图", raw_block="mock", start_pos=0, end_pos=0)
    ]

    print(f"🔥 Launching {len(directives)} concurrent sub-agent tasks...")
    start_time = time.time()
    
    tasks = [agent.fulfill_directive_async(d, state) for d in directives]
    results = await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    print(f"\n✅ All tasks completed in {duration:.2f}s")
    
    print("\n--- Summary ---")
    for i, (success, asset, html) in enumerate(results):
        status = "✅ PASS" if success else "❌ FAIL"
        aid = directives[i].id
        vqa_status = asset.vqa_status if asset else "N/A"
        print(f"- {aid}: {status} | Asset: {asset.id if asset else 'None'} | VQA: {vqa_status}")
        if success:
            print(f"  [HTML] {html[:80]}...")

if __name__ == "__main__":
    asyncio.run(run_subagent_test())
