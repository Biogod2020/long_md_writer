import asyncio
import os
import shutil
import time
from pathlib import Path
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, SectionInfo

async def run_e2e_integration_test():
    print("🌟 [E2E INTEGRATION TEST] Verifying SOTA 2.0 Async Fulfillment Pipeline...")
    
    client = GeminiClient()
    agent = AssetFulfillmentAgent(client=client, debug=True, max_concurrency=4)
    
    ws_id = f"e2e_sourcing_{int(time.time())}"
    ws_path = Path(f"workspaces/workspace/{ws_id}")
    ws_path.mkdir(parents=True, exist_ok=True)
    
    # 1. 准备测试 Markdown (混合意图)
    md_content = """# Section 1: Entity Test
In this section, we discuss the visual identity of GZ2HS.

:::visual
{
  "id": "gz2hs-uniform",
  "action": "SEARCH_WEB",
  "description": "广州市第二中学的日常运动服校服照片，绿白配色"
}
:::

And here is a diagram of the Transformer mechanism.

:::visual
{
  "id": "transformer-fig",
  "action": "SEARCH_WEB",
  "description": "Transformer 论文 Figure 1 原始架构图"
}
:::

:::visual
{
  "id": "bert-attention-detail",
  "action": "SEARCH_WEB",
  "description": "BERT Encoder 内部的 Multi-head Attention 机制细节图"
}
:::
"""
    sec_path = ws_path / "sec-1.md"
    sec_path.write_text(md_content, encoding="utf-8")
    
    state = AgentState(
        job_id=ws_id,
        workspace_path=str(ws_path),
        manifest=Manifest(project_title="E2E Integration", description="SOTA 2.0 Test", sections=[]),
        completed_md_sections=[str(sec_path)]
    )
    
    # 2. 执行全量并行履行
    print("🔥 Launching SOTA 2.0 Parallel Fulfillment...")
    start_time = time.time()
    await agent.run_parallel_async(state)
    duration = time.time() - start_time
    
    print(f"\n✅ E2E Pipeline completed in {duration:.2f}s")
    
    # 3. 验证产物
    final_content = sec_path.read_text(encoding="utf-8")
    print("\n--- Final Markdown Snippet ---")
    print(final_content[:500])
    
    if "<figure>" in final_content and "assets/images/" in final_content:
        print("\n🏆 SUCCESS: Visual directives replaced with real assets!")
    else:
        print("\n❌ FAILURE: Replacement logic or sourcing failed.")

if __name__ == "__main__":
    asyncio.run(run_e2e_integration_test())
