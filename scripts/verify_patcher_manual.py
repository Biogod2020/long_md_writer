import asyncio
import json
from pathlib import Path
from src.core.types import AgentState
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.orchestration.breakpoint_manager import SnapshotManager

async def verify_fix():
    job_id = "final_e2e_v2"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    
    # 1. 初始化状态 (从最近的快照加载)
    # 我们假设物理文件已经被之前的 --jump 恢复了
    snapshot_id = "BP-8_Assets_Done_010124"
    print(f"🔬 [MANUAL VERIFY] Loading state from {snapshot_id}...")
    
    # 物理恢复 (确保文件在原地)
    state_path = workspace_path / "snapshots" / snapshot_id / "state.json"
    state_data = json.loads(state_path.read_text())
    state = AgentState(**state_data)
    
    # 2. 检查当前文稿中的残留指令数
    def count_residue():
        import re
        total = 0
        for f in Path(state.workspace_path).glob("md/*.md"):
            if ".working" in f.name: continue
            content = f.read_text()
            matches = re.findall(r":::visual", content)
            total += len(matches)
        return total

    print(f"📊 Before Fix: {count_residue()} lingering directives found.")

    # 3. 运行加固后的履约 Agent
    agent = AssetFulfillmentAgent(debug=True)
    print("🚀 Running hardened fulfillment write-back...")
    
    # 强制标记为未完成以触发逻辑
    state.batch_fulfillment_complete = False
    
    await agent.run_parallel_async(state)

    # 4. 最终检查
    final_count = count_residue()
    print(f"📊 After Fix: {final_count} lingering directives found.")

    if final_count == 0:
        print("\n🏆 SUCCESS! The new 'Final Defense Line' logic automatically erased all ghosts.")
    else:
        print("\n💀 FAILED. Residue still exists.")

if __name__ == "__main__":
    asyncio.run(verify_fix())