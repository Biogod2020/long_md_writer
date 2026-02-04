import asyncio
from pathlib import Path
from src.core.types import AgentState
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient

async def test_mixed_fulfillment():
    workspace = Path("workspace/mix_fulfillment_test")
    client = GeminiClient()
    
    state = AgentState(
        job_id="mix_test",
        workspace_path=str(workspace),
        completed_md_sections=[str(workspace / "md" / "section_mixed.md")],
        uar_path=str(workspace / "assets.json"),
        debug_mode=True
    )
    
    # 确保 UAR 已初始化
    state.initialize_uar()
    
    print("\n🚀 [Test] 启动混合履约任务...")
    agent = AssetFulfillmentAgent(
        client=client,
        skip_generation=False,
        skip_search=False, # 启用搜索
        debug=True
    )
    
    # 运行履约
    updated_state = await agent.run_parallel_async(state)
    
    print("\n✅ [Test] 履约完成。检查产出...")
    
    # 验证文件
    generated = list((workspace / "agent_generated").glob("mix-v1.svg"))
    sourced = list((workspace / "agent_sourced").glob("mix-v2.*"))
    
    print(f"  - 生成资产 (SVG): {'✓' if generated else '✗'}")
    print(f"  - 搜索资产 (Image): {'✓' if sourced else '✗'}")
    
    # 验证 Markdown 回写
    md_content = (workspace / "md" / "section_mixed.md").read_text()
    has_figure = "<figure>" in md_content
    print(f"  - Markdown 物理固化: {'✓' if has_figure else '✗'}")

if __name__ == "__main__":
    asyncio.run(test_mixed_fulfillment())
