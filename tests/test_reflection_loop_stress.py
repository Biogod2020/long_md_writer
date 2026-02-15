import asyncio
import os
import shutil
import time
from pathlib import Path
from src.agents.image_sourcing.agent import ImageSourcingAgent
from src.agents.asset_management.models import VisualDirective
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, SectionInfo

async def run_reflection_stress():
    print("🔥 [STRESS TEST] Verification of Reflection Loop & Self-Correction...")
    
    client = GeminiClient()
    agent = ImageSourcingAgent(client=client, debug=True, headless=True)
    
    ws_id = f"stress_reflection_{int(time.time())}"
    ws_path = Path(f"workspaces/workspace/{ws_id}")
    ws_path.mkdir(parents=True, exist_ok=True)
    
    state = AgentState(
        job_id=ws_id,
        workspace_path=str(ws_path),
        manifest=Manifest(project_title="Reflection Stress", description="Testing Pivot Logic", sections=[])
    )
    
    directives = [
        VisualDirective(
            id="gz2hs-flag", 
            description="广州市第二中学的校旗图片，旗帜上应有明显的校徽和校名", 
            raw_block="mock", start_pos=0, end_pos=0
        ),
        VisualDirective(
            id="yujintai-lab", 
            description="郁金泰研究员在实验室近距离操作脑部扫描仪或精密实验仪器的照片", 
            raw_block="mock", start_pos=0, end_pos=0
        ),
        VisualDirective(
            id="bert-encoder-detail", 
            description="BERT 模型架构中具体到单个 Encoder Block 内部 Multi-head Attention 机制的细节原理图", 
            raw_block="mock", start_pos=0, end_pos=0
        )
    ]

    print(f"🔥 Launching {len(directives)} difficult tasks concurrently...")
    start_time = time.time()
    
    tasks = [agent.fulfill_directive_async(d, state) for d in directives]
    results = await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    print(f"\n✅ All reflection trials completed in {duration:.2f}s")
    
    print("\n--- Reflection Audit ---")
    for i, (success, asset, html) in enumerate(results):
        status = "✅ FIXED" if success else "❌ GAVE UP"
        aid = directives[i].id
        vqa_status = asset.vqa_status if asset else "N/A"
        print(f"- {aid}: {status} | Asset: {asset.id if asset else 'None'} | VQA: {vqa_status}")

if __name__ == "__main__":
    asyncio.run(run_reflection_stress())
