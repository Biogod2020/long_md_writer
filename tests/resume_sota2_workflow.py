import asyncio
import sys
import uuid
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.workflow_markdown import create_sota2_workflow
from src.core.types import AgentState, UniversalAssetRegistry
from src.core.gemini_client import GeminiClient

# ============================================================================ 
# 恢复配置
# ============================================================================ 

RESUME_JOB_ID = "sota2_20260120_164630"
WORKSPACE_DIR = Path("workspace") / RESUME_JOB_ID
INPUTS_DIR = Path("inputs")
FIXED_THREAD_ID = "resume-session-001" 

AUTO_ANSWERS = {
    "q0": "确认使用向量点积（dot product）来定量描述心脏向量在各导联轴上的投影，以符合目标读者群体的数学物理基础。",
    "q1": "确认引入交互式 JavaScript 动态模拟器组件，用于展示心脏向量在 Einthoven 三角边上的动态投影变化。",
    "q2": "详细推导威尔逊中央电端（WCT）的物理原理，将其作为建立单极导联概念的 First Principles 根基。",
    "q3": "严格遵循第一章的 CSS 风格和排版布局，启用公式折叠和侧边栏术语表功能以优化长文阅读体验。"
}

async def interactive_resume():
    print(f"\n🚀 启动 SOTA 2.0 交互式恢复流程 (Job: {RESUME_JOB_ID})")
    
    # 1. 初始化基础组件
    client = GeminiClient()
    app = create_sota2_workflow(client=client)
    config = {"configurable": {"thread_id": FIXED_THREAD_ID}}

    # 2. 构造或检查状态
    state_info = app.get_state(config)
    
    if not state_info.values:
        print("  ⚡ 初始启动：正在注入 UAR 现场与澄清答案...")
        prompt_file = INPUTS_DIR / "prompt.txt"
        user_intent = prompt_file.read_text(encoding="utf-8")
        
        state = AgentState(
            job_id=RESUME_JOB_ID,
            workspace_path=str(WORKSPACE_DIR),
            user_intent=user_intent,
            debug_mode=True,
            uar_path=str(WORKSPACE_DIR / "assets.json")
        )
        state.initialize_uar()
        state.clarifier_answers = AUTO_ANSWERS
        
        # 强行引导至 refiner 之前的点
        app.update_state(config, state.model_dump(), as_node="clarifier")
    else:
        print("  ✓ 检测到已有 Thread 状态，继续执行...")

    # 3. 交互运行循环
    while True:
        try:
            print("\n" + "."*30 + " 执行工作流 " + "."*30)
            last_state = None
            async for event in app.astream(None, config=config, stream_mode="values"):
                last_state = event

            # 检查是否由于中断而结束
            state_info = app.get_state(config)
            if not state_info.next:
                print("\n✅ 工作流已成功运行至终点 (END)")
                break

            next_node = state_info.next[0]
            current_values = AgentState(**state_info.values) if isinstance(state_info.values, dict) else state_info.values
            
            print(f"\n[HITL 中断] 流程停在: {next_node}")
            update_data = {}

            if next_node == "review_brief":
                print("\n" + "="*20 + " PROJECT BRIEF 审核 " + "="*20)
                print(current_values.project_brief[:2000])
                print("="*60)
                cmd = input("\n输入 'y' 通过，或输入建议: ").strip().lower()
                if cmd in ['y', 'yes', 'approve', '']:
                    update_data = {"brief_approved": True}
                else:
                    update_data = {"brief_approved": False, "user_brief_feedback": cmd}

            elif next_node == "review_outline":
                print("\n" + "="*20 + " MANIFEST (大纲) 审核 " + "="*20)
                if current_values.manifest:
                    print(f"标题: {current_values.manifest.project_title}")
                    for s in current_values.manifest.sections:
                        print(f"  - {s.id}: {s.title}")
                print("="*60)
                cmd = input("\n输入 'y' 通过，或输入建议: ").strip().lower()
                if cmd in ['y', 'yes', 'approve', '']:
                    update_data = {"outline_approved": True}
                else:
                    update_data = {"outline_approved": False, "user_outline_feedback": cmd}

            elif next_node == "markdown_review":
                print(f"\n📋 Markdown 审核 (已完成 {len(current_values.completed_md_sections)} 章节)")
                cmd = input("\n输入 'y' 通过，或输入建议: ").strip().lower()
                if cmd in ['y', 'yes', 'approve', '']:
                    update_data = {"markdown_approved": True}
                else:
                    update_data = {"markdown_approved": False, "user_markdown_feedback": cmd}

            # 更新状态并继续
            if update_data:
                app.update_state(config, update_data)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户请求中断。状态已保存。\n")
            break
        except Exception as e:
            print(f"\n❌ 运行异常: {e}")
            import traceback
            traceback.print_exc()
            break

if __name__ == "__main__":
    asyncio.run(interactive_resume())
