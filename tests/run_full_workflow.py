"""
完整 SOTA 2.0 工作流测试

使用 LangGraph 已有的 workflow 运行完整流程：
Clarifier → Refiner → Architect → TechSpec → Writer(循环) → MarkdownQA

测试到 Markdown 生成阶段为止
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.workflow_html import run_workflow


# ============================================================================
# 输入配置
# ============================================================================

INPUTS_DIR = Path(__file__).parent.parent / "inputs"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "images" / "candidates_ecg-medication-effects"

def load_inputs():
    """加载所有输入文件"""
    # 加载用户 prompt
    prompt_file = INPUTS_DIR / "prompt.txt"
    user_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""

    # 加载原始素材
    raw_files = [
        "Cardiovascular_markdown.md",
        "ECG Pathology and Clinical Features.md",
        "ecg_qa.md",
        "从偶极子到心电图.html",
    ]

    materials = []
    for filename in raw_files:
        file_path = INPUTS_DIR / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            materials.append(f"# 📄 {filename}\n\n{content}\n")
            print(f"  ✓ 加载 {filename} ({len(content):,} 字符)")

    raw_materials = "\n\n---\n\n".join(materials)

    # 组合 prompt 和素材
    full_input = f"""# 用户需求

{user_prompt}

# 原始素材

{raw_materials}
"""

    return full_input


async def main():
    """运行完整工作流"""
    print("\n" + "=" * 70)
    print(" SOTA 2.0 完整工作流测试 (LangGraph)")
    print("=" * 70)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"full_{timestamp}"

    print(f"\n📋 Job ID: {job_id}")
    print(f"📁 工作目录: ./workspaces/workspace/{job_id}")

    # 加载输入
    print("\n--- 加载输入 ---")
    raw_materials = load_inputs()
    print(f"\n  总输入长度: {len(raw_materials):,} 字符")

    # 运行工作流
    print("\n--- 启动 LangGraph 工作流 ---")
    print("流程: Clarifier → Refiner → Architect → TechSpec → Writer → MarkdownQA")
    print("\n⚠️  注意: 工作流会在以下节点暂停等待人工审核:")
    print("  - review_brief: Brief 审核")
    print("  - review_outline: 大纲审核")
    print("  - markdown_review: Markdown 审核")
    print("\n" + "-" * 70)

    try:
        final_state = await run_workflow(
            raw_materials=raw_materials,
            workspace_base="./workspace",
            job_id=job_id,
            debug_mode=True,
            skip_markdown_qa=False,
        )

        print("\n" + "=" * 70)
        print(" 工作流完成")
        print("=" * 70)

        # 输出结果摘要
        print("\n📊 结果摘要:")
        print(f"  - Job ID: {final_state.job_id}")
        print(f"  - 工作目录: {final_state.workspace_path}")

        if final_state.manifest:
            print(f"  - 项目标题: {final_state.manifest.project_title}")
            print(f"  - 章节数量: {len(final_state.manifest.sections)}")
            for sec in final_state.manifest.sections:
                print(f"    - {sec.id}: {sec.title} ({sec.estimated_words} 字)")

        print(f"  - 已完成 Markdown: {len(final_state.completed_md_sections)} 个")
        for md_path in final_state.completed_md_sections:
            print(f"    - {Path(md_path).name}")

        if final_state.errors:
            print("\n❌ 错误:")
            for err in final_state.errors:
                print(f"  - {err}")

        return final_state

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 工作流错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
