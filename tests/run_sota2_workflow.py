"""
SOTA 2.0 完整工作流测试

使用新的 SOTA 2.0 LangGraph workflow 运行完整流程：
AssetIndexer → Clarifier → Refiner → Architect → TechSpec
→ Writer(循环) → Fulfillment → Critic → EditorialQA

测试到 Markdown 生成阶段为止。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.workflow_markdown import run_sota2_workflow


# ============================================================================
# 输入配置
# ============================================================================

INPUTS_DIR = Path(__file__).parent.parent / "inputs"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "images" / "candidates_ecg-medication-effects"


def load_inputs():
    """加载所有输入文件

    Returns:
        user_intent: 用户意图/指令 (告诉 AI 做什么)
        reference_materials: 参考资料全文 (知识/数据，供创作参考)
    """
    print("\n--- 加载输入文件 ---")

    # 加载用户意图 (prompt.txt)
    prompt_file = INPUTS_DIR / "prompt.txt"
    user_intent = ""
    if prompt_file.exists():
        user_intent = prompt_file.read_text(encoding="utf-8")
        print(f"  ✓ prompt.txt (用户意图: {len(user_intent)} 字符)")

    # 加载参考资料
    reference_files = [
        "从偶极子到心电图.html",      # 风格参考
        "ecg_qa.md",                    # QA 知识
        "ECG Pathology and Clinical Features.md",  # 病理特征
        "Cardiovascular_markdown.md",   # 心血管知识
    ]

    materials = []
    for filename in reference_files:
        file_path = INPUTS_DIR / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            materials.append(f"# 📄 {filename}\n\n{content}\n")
            print(f"  ✓ {filename} ({len(content):,} 字符)")

    reference_materials = "\n\n---\n\n".join(materials)
    print(f"\n  总参考资料长度: {len(reference_materials):,} 字符")

    return user_intent, reference_materials


async def main():
    """运行 SOTA 2.0 完整工作流"""
    import argparse
    parser = argparse.ArgumentParser(description="Run SOTA 2.0 Workflow")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--auto", action="store_true", help="Enable auto mode (bypass human-in-the-loop)")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(" SOTA 2.0 完整工作流测试")
    print("=" * 70)
    
    if args.auto:
        print("  🚀 [AUTO MODE] Enabled. Human intervention will be bypassed.")

    # 加载输入
    user_intent, reference_materials = load_inputs()

    # 运行工作流
    print("\n--- 启动 SOTA 2.0 工作流 ---")

    # 定义挂载的资产库
    mounted = {
        "cardiology_global": str(INPUTS_DIR.parent / "data" / "global_asset_lib" / "master_assets.json")
    }

    try:
        final_state = await run_sota2_workflow(
            user_intent=user_intent,
            reference_materials=reference_materials,
            assets_input_dir=str(ASSETS_DIR),
            workspace_base="./workspace",
            skip_vision=False,
            skip_asset_audit=False,
            debug_mode=args.debug,
            mounted_workspaces=mounted,
            auto_mode=args.auto
        )

        print("\n" + "=" * 70)
        print(" 工作流完成")
        print("=" * 70)

        # 输出结果摘要
        print("\n📊 结果摘要:")
        print(f"  Job ID: {final_state.job_id}")
        print(f"  工作目录: {final_state.workspace_path}")

        if final_state.manifest:
            print("\n📚 Manifest:")
            print(f"  标题: {final_state.manifest.project_title}")
            print(f"  章节数: {len(final_state.manifest.sections)}")
            for sec in final_state.manifest.sections:
                status = "✅" if sec.file_path else "⏳"
                print(f"    {status} {sec.id}: {sec.title} (~{sec.estimated_words} 字)")

        if final_state.completed_md_sections:
            print("\n📝 已完成 Markdown:")
            for md_path in final_state.completed_md_sections:
                p = Path(md_path)
                if p.exists():
                    content = p.read_text(encoding="utf-8")
                    print(f"    - {p.name} ({len(content):,} 字符)")
                else:
                    print(f"    - {p.name} (文件不存在)")

        if final_state.asset_registry:
            uar = final_state.asset_registry
            print("\n🎨 资产注册表 (UAR):")
            print(f"  总资产数: {len(uar.assets)}")
            by_source = {}
            for asset in uar.assets.values():
                src = asset.source.value
                by_source[src] = by_source.get(src, 0) + 1
            for src, count in by_source.items():
                print(f"    - {src}: {count} 个")

        if final_state.errors:
            print("\n❌ 错误:")
            for err in final_state.errors:
                print(f"  - {err}")

        return final_state

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 工作流错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
