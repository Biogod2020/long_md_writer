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
    """加载所有输入文件"""
    print("\n--- 加载输入文件 ---")

    # 加载用户 prompt
    prompt_file = INPUTS_DIR / "prompt.txt"
    user_prompt = ""
    if prompt_file.exists():
        user_prompt = prompt_file.read_text(encoding="utf-8")
        print(f"  ✓ prompt.txt ({len(user_prompt)} 字符)")

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
            print(f"  ✓ {filename} ({len(content):,} 字符)")

    raw_materials = "\n\n---\n\n".join(materials)
    print(f"\n  总素材长度: {len(raw_materials):,} 字符")

    return user_prompt, raw_materials


async def main():
    """运行 SOTA 2.0 完整工作流"""
    print("\n" + "=" * 70)
    print(" SOTA 2.0 完整工作流测试")
    print("=" * 70)
    print("""
流程:
  1. AssetIndexer - 资产索引 + VLM 贴标
  2. Clarifier - 需求澄清问题
  3. Refiner - 生成 Project Brief
  4. Architect - 生成 Manifest (多章节规划)
  5. TechSpec - 技术规格
  6. Writer (循环) - 逐章节写作
  7. AssetFulfillment - 资产履约 (:::visual → SVG)
  8. AssetCritic - 资产审计
  9. EditorialQA - 全量语义审核
  10. MarkdownQA - Markdown 质检

⚠️  工作流会在以下节点暂停等待人工输入:
  - clarifier → refiner: 回答澄清问题
  - review_brief: 审核 Brief
  - review_outline: 审核大纲 (Manifest)
  - markdown_review: 审核 Markdown
""")

    # 加载输入
    user_prompt, raw_materials = load_inputs()

    # 运行工作流
    print("\n--- 启动 SOTA 2.0 工作流 ---")

    try:
        final_state = await run_sota2_workflow(
            raw_materials=raw_materials,
            user_prompt=user_prompt,
            assets_input_dir=str(ASSETS_DIR),
            workspace_base="./workspace",
            skip_vision=False,  # 启用 VLM 贴标
            skip_asset_audit=False,  # 启用资产审计
            debug_mode=True,
        )

        print("\n" + "=" * 70)
        print(" 工作流完成")
        print("=" * 70)

        # 输出结果摘要
        print(f"\n📊 结果摘要:")
        print(f"  Job ID: {final_state.job_id}")
        print(f"  工作目录: {final_state.workspace_path}")

        if final_state.manifest:
            print(f"\n📚 Manifest:")
            print(f"  标题: {final_state.manifest.project_title}")
            print(f"  章节数: {len(final_state.manifest.sections)}")
            for sec in final_state.manifest.sections:
                status = "✅" if sec.file_path else "⏳"
                print(f"    {status} {sec.id}: {sec.title} (~{sec.estimated_words} 字)")

        if final_state.completed_md_sections:
            print(f"\n📝 已完成 Markdown:")
            for md_path in final_state.completed_md_sections:
                p = Path(md_path)
                if p.exists():
                    content = p.read_text(encoding="utf-8")
                    print(f"    - {p.name} ({len(content):,} 字符)")
                else:
                    print(f"    - {p.name} (文件不存在)")

        if final_state.asset_registry:
            uar = final_state.asset_registry
            print(f"\n🎨 资产注册表 (UAR):")
            print(f"  总资产数: {len(uar.assets)}")
            by_source = {}
            for asset in uar.assets.values():
                src = asset.source.value
                by_source[src] = by_source.get(src, 0) + 1
            for src, count in by_source.items():
                print(f"    - {src}: {count} 个")

        if final_state.errors:
            print(f"\n❌ 错误:")
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
