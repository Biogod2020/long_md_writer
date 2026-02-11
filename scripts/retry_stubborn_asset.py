
import asyncio
import json
import re
from pathlib import Path
from src.core.types import AgentState
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent

async def retry_surgery():
    job_id = "final_v3"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    
    print(f"🚀 [SURGERY] Targeted retry for stubborn asset: s5-fig-reciprocal-logic")
    
    # 1. 加载最近的 BP-8 状态
    snapshot_dir = list(workspace_path.glob("snapshots/BP-8_Assets_Done_*"))[-1]
    state_data = json.loads((snapshot_dir / "state.json").read_text())
    state = AgentState(**state_data)
    
    # 2. 修改状态，只针对那一个失败的指令
    md_path = workspace_path / "md/s5-clinical-05.md"
    content = md_path.read_text()
    
    # 构造虚假的指令对象，触发 Agent
    agent = AssetFulfillmentAgent(debug=True)
    directives = agent._parse_visual_directives(content)
    
    # 过滤出我们需要重试的那一个
    target_d = [d for d in directives if d.id == "s5-fig-reciprocal-logic"]
    
    if not target_d:
        print("❌ Could not find the directive in s5-clinical-05.md")
        return

    print(f"🔥 Found target. Starting generation with 5-attempt limit...")
    
    # 3. 运行履约 (直接调用 worker 的核心逻辑)
    uar = state.get_uar()
    gen_path = workspace_path / "agent_generated"
    src_path = workspace_path / "agent_sourced"
    
    # 强制清理该资产在 UAR 中的旧记录（如果有）
    if target_d[0].id in uar.assets:
        del uar.assets[target_d[0].id]

    trace = {"id": target_d[0].id, "steps": []}
    result_d, new_asset = await agent._fulfill_directive_async(
        target_d[0], uar, gen_path, src_path, "s5", workspace_path, state, trace,
        target_file=md_path
    )

    if result_d.fulfilled:
        print(f"✅ SUCCESS! Asset generated and verified after extra attempts.")
        # 4. 物理回填
        if new_asset:
            uar.register_immediate(new_asset)
        
        # 使用防弹逻辑回填
        new_content = content.replace(target_d[0].raw_block, result_d.result_html)
        md_path.write_text(new_content)
        print(f"💾 Physical file s5-clinical-05.md updated.")
    else:
        print(f"💀 FAILED again. Error: {result_d.error}")

if __name__ == "__main__":
    asyncio.run(retry_surgery())
