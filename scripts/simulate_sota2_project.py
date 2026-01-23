#!/usr/bin/env python3
"""
模拟 LangGraph 生产场景：跨项目使用全局资产库

场景描述：
1. 我们建立了一个全局资产池 (data/global_asset_lib) 并在 master_assets.json 中存储了 AI 语义标签。
2. 开启一个新项目 (simulate_project_001)。
3. 项目启动时挂载全局 UAR。
4. 运行 AssetIndexerAgent，确认它能识别“已在全局库中扫描过”的资产，跳过 Vision API。
5. 模拟 WriterAgent 通过语义搜索从全局库中精准定位资产。
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, AssetSource
from src.agents.asset_management import AssetIndexerAgent

async def simulate_workflow():
    print("\n" + "="*70)
    print(" 🚀 模拟 SOTA 2.0 生产环境：全局资产共享测试")
    print("="*70)

    # 1. 模拟环境配置
    WORKSPACE_BASE = PROJECT_ROOT / "workspace" / "simulation_test"
    WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
    
    GLOBAL_UAR_PATH = PROJECT_ROOT / "data" / "global_asset_lib" / "master_assets.json"
    
    # 模拟项目状态
    state = AgentState(
        job_id="sim_2026_01",
        workspace_path=str(WORKSPACE_BASE),
        user_intent="写一篇关于心脏起搏点和药物对心电图影响的文章",
        uar_path=str(GLOBAL_UAR_PATH) # 核心：挂载全局索引
    )
    
    # 检查全局索引是否存在
    if not GLOBAL_UAR_PATH.exists():
        print(f"❌ 错误: 全局索引文件不存在 ({GLOBAL_UAR_PATH})，请先运行 reindex_global_lib.py")
        return

    print(f"📁 项目工作区: {state.workspace_path}")
    print(f"🔗 挂载全局资产库: {GLOBAL_UAR_PATH}")

    # 2. 模拟节点：AssetIndexerAgent (Phase 0)
    # 目标：扫描同一个目录，但由于 UAR 已有记录，应全部跳过 API 调用
    print(f"\n[Node: AssetIndexer] 执行资产同步...")
    client = GeminiClient()
    
    # 强制不使用 skip_vision，看看它是否够聪明能利用 UAR 的去重逻辑
    indexer = AssetIndexerAgent(client=client, skip_vision=False)
    
    # 真实场景中是从 state 读取 UAR
    # 我们指向同样的目录测试去重
    INPUT_DIR = PROJECT_ROOT / "data" / "global_asset_lib" / "images"
    
    start_uar_count = len(state.get_uar().assets)
    print(f"   📊 初始 UAR 资产数: {start_uar_count}")
    
    # 执行同步 (使用 run_async)
    state = await indexer.run_async(state)
    
    end_uar_count = len(state.get_uar().assets)
    print(f"   📊 运行后 UAR 资产数: {end_uar_count}")
    print(f"   ✅ 同步结果：新增了 {end_uar_count - start_uar_count} 个新资产 (应为 0, 因为全部命中了去重)")

    # 3. 模拟节点：WriterAgent 语义匹配 (核心生产力)
    # 场景：Writer 想要一张“心脏解剖图”，看看能不能从全局库里搜出来
    print(f"\n[Node: Writer] 模拟语义搜索...")
    uar = state.get_uar()
    
    test_query = "心脏解剖结构示意图，包含心房和心室"
    print(f"   🔍 Writer 意图: '{test_query}'")
    
    # 获取候选清单 (底层逻辑：获取所有可复用资产)
    candidates = uar.intent_match_candidates(test_query, client=client, limit=5)
    
    print(f"   📦 UAR 返回了 {len(candidates)} 个候选资产:")
    for i, asset in enumerate(candidates):
        print(f"     [{i+1}] ID: {asset.id} | Label: {asset.semantic_label}")
        
    if candidates:
        print(f"\n✨ 结论：项目成功识别了全局库中的资产，Writer 现在可以直接注入这些图片而无需重新扫描！")
    else:
        print(f"\n⚠️ 未找到候选资产，请确认 reindex 脚本是否成功生成了语义标签。")

    print("\n" + "="*70)
    print(" ✅ 生产环境模拟完成")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(simulate_workflow())
