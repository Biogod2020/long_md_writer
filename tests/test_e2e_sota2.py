"""
SOTA 2.0 端到端测试

使用真实 LLM 调用测试完整流程：
1. AssetIndexerAgent - 索引资产
2. WriterAgent - 创作章节
3. AssetFulfillmentAgent - 履约视觉指令
4. AssetCriticAgent - 审计资产
5. MarkdownValidator - 校验输出
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.types import (
    AgentState,
    Manifest,
    SectionInfo,
)
from src.agents.asset_indexer_agent import AssetIndexerAgent
from src.agents.writer_agent import WriterAgent
from src.agents.asset_fulfillment_agent import AssetFulfillmentAgent
from src.agents.asset_critic_agent import AssetCriticAgent
from src.core.validators import MarkdownValidator


def load_raw_materials(base_path: Path) -> str:
    """加载原始素材"""
    materials = []

    text_files = [
        "Cardiovascular_markdown.md",
        "ECG Pathology and Clinical Features.md",
        "ecg_qa.md",
    ]

    for filename in text_files:
        file_path = base_path / filename
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            materials.append(f"# 📄 {filename}\n\n{content}\n")
            print(f"  ✓ 加载 {filename} ({len(content):,} 字符)")

    html_file = base_path / "从偶极子到心电图.html"
    if html_file.exists():
        content = html_file.read_text(encoding="utf-8")
        materials.append(f"# 📄 从偶极子到心电图.html\n\n{content}\n")
        print(f"  ✓ 加载 从偶极子到心电图.html ({len(content):,} 字符)")

    return "\n\n---\n\n".join(materials)


def load_user_prompt(base_path: Path) -> str:
    """加载用户指令"""
    prompt_file = base_path / "prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""


async def run_e2e_test():
    """运行端到端测试"""
    print("\n" + "=" * 70)
    print("SOTA 2.0 端到端测试 (真实 LLM 调用)")
    print("=" * 70)

    project_root = Path(__file__).parent.parent
    inputs_dir = project_root / "inputs"
    assets_dir = project_root / "assets" / "images"

    # 创建工作目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir = project_root / "workspace_test" / f"e2e_{timestamp}"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n工作目录: {workspace_dir}")

    # =========================================================================
    # 步骤 1: 加载输入
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 1: 加载输入")
    print("-" * 70)

    raw_materials = load_raw_materials(inputs_dir)
    user_prompt = load_user_prompt(inputs_dir)

    print(f"\n  用户指令: {user_prompt[:100]}...")
    print(f"  原始素材总长度: {len(raw_materials):,} 字符")

    # 创建状态
    state = AgentState(
        job_id=f"e2e-{timestamp}",
        workspace_path=str(workspace_dir),
        raw_materials=raw_materials,
        project_brief=user_prompt
    )

    # =========================================================================
    # 步骤 2: 资产索引
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 2: 资产索引 (AssetIndexerAgent)")
    print("-" * 70)

    # 初始化 UAR
    uar = state.initialize_uar()

    # 如果 assets 目录存在且有图片，使用 AssetIndexerAgent
    if assets_dir.exists():
        indexer = AssetIndexerAgent(
            input_dir=str(assets_dir),
            skip_vision=True  # 跳过 Vision API 以加快测试
        )
        state = indexer.run(state)
        print(f"  注册的资产数量: {len(uar.assets)}")
    else:
        print(f"  资产目录不存在: {assets_dir}")

    # 注意: 不添加虚假的模拟资产
    # 如果没有真实图片，Writer 会使用 :::visual 指令请求生成 SVG
    if len(uar.assets) == 0:
        print("  UAR 为空，Writer 将依赖 :::visual 指令生成所需图形")

    # =========================================================================
    # 步骤 3: 创建 Manifest
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 3: 创建项目清单 (Manifest)")
    print("-" * 70)

    state.manifest = Manifest(
        project_title="心电图物理原理教程 - 第二章",
        description='从导线到导联——我们如何全方位"观"心',
        sections=[
            SectionInfo(
                id="sec-2-1",
                title="导联的基本概念",
                summary="介绍心电导联的基本概念，包括标准导联和加压导联的区别，以及导联系统如何帮助我们从不同角度观察心脏电活动",
                estimated_words=2000,
                metadata={"namespace": "s1", "visual_intent": "需要导联位置示意图、Einthoven三角图"}
            ),
        ]
    )

    print(f"  项目标题: {state.manifest.project_title}")
    print(f"  章节数量: {len(state.manifest.sections)}")
    for sec in state.manifest.sections:
        print(f"    - {sec.id}: {sec.title}")

    # =========================================================================
    # 步骤 4: Writer 创作
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 4: Writer 创作 (WriterAgent)")
    print("-" * 70)

    writer = WriterAgent()
    state.current_section_index = 0

    print("  开始创作章节...")
    print("  (这可能需要 1-3 分钟)")

    try:
        state = await writer.run(state)

        # 获取创作内容 - 从保存的文件读取
        section = state.manifest.sections[0]
        md_output_path = workspace_dir / "md" / f"{section.id}.md"

        if md_output_path.exists():
            writer_output = md_output_path.read_text(encoding="utf-8")
        else:
            # 尝试从 state 获取
            if isinstance(state.completed_md_sections, dict):
                writer_output = state.completed_md_sections.get(section.id, "")
            elif isinstance(state.completed_md_sections, list) and state.completed_md_sections:
                first_entry = state.completed_md_sections[0]
                first_path = Path(first_entry)
                if first_path.exists():
                    writer_output = first_path.read_text(encoding="utf-8")
                else:
                    writer_output = first_entry
            else:
                writer_output = ""

        print("\n  创作完成!")
        print(f"  输出长度: {len(writer_output):,} 字符")

        # 保存 Writer 输出
        writer_output_path = workspace_dir / "writer_output.md"
        writer_output_path.write_text(writer_output, encoding="utf-8")
        print(f"  已保存到: {writer_output_path}")

        # 预览
        print("\n  输出预览 (前 500 字符):")
        print("-" * 40)
        print(writer_output[:500])
        print("-" * 40)

    except Exception as e:
        print(f"\n  ✗ Writer 创作失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # =========================================================================
    # 步骤 5: 资产履约
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 5: 资产履约 (AssetFulfillmentAgent)")
    print("-" * 70)

    fulfillment_agent = AssetFulfillmentAgent(
        skip_generation=False,  # 真实生成 SVG
        skip_search=True  # 跳过网络搜索
    )

    namespace = state.manifest.sections[0].metadata.get("namespace", "s1")
    state, fulfilled_content = await fulfillment_agent.run_async(state, writer_output, namespace)

    print("\n  履约完成!")
    print(f"  输出长度: {len(fulfilled_content):,} 字符")

    # 检查是否还有未处理的 :::visual
    remaining_visuals = fulfilled_content.count(":::visual")
    print(f"  剩余未处理的 :::visual: {remaining_visuals}")

    # 保存履约后的输出
    fulfilled_output_path = workspace_dir / "fulfilled_output.md"
    fulfilled_output_path.write_text(fulfilled_content, encoding="utf-8")
    print(f"  已保存到: {fulfilled_output_path}")

    # =========================================================================
    # 步骤 6: 资产审计
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 6: 资产审计 (AssetCriticAgent)")
    print("-" * 70)

    critic = AssetCriticAgent(skip_audit=False)
    directives = fulfillment_agent._parse_visual_directives(writer_output)
    assets_with_intents = []
    for directive in directives:
        asset = state.asset_registry.get_asset(directive.id) if state.asset_registry else None
        if asset:
            assets_with_intents.append((asset, directive.description))

    audit_reports = []
    if assets_with_intents:
        audit_reports = await critic.batch_audit_async(
            assets_with_intents,
            workspace_path=Path(state.workspace_path)
        )
        failed_reports = [r for r in audit_reports if not r.is_acceptable]
        print(f"  审计完成: {len(audit_reports)} 个资产, 失败 {len(failed_reports)} 个")
    else:
        print("  无可审计资产 (未生成 :::visual 或未找到匹配资产)")

    # =========================================================================
    # 步骤 7: Markdown 校验
    # =========================================================================
    print("\n" + "-" * 70)
    print("步骤 7: Markdown 校验 (MarkdownValidator)")
    print("-" * 70)

    validator = MarkdownValidator()
    result = validator.validate_all(fulfilled_content, namespace=namespace)

    print(f"\n  校验结果: {'✓ 通过' if result.is_valid else '✗ 失败'}")
    print(f"  问题数量: {len(result.issues)}")

    if result.issues:
        print("\n  问题列表:")
        for issue in result.issues[:10]:
            print(f"    - [{issue.severity.value}] {issue.message[:60]}...")

    # =========================================================================
    # 最终报告
    # =========================================================================
    print("\n" + "=" * 70)
    print("端到端测试完成")
    print("=" * 70)

    audit_fail_count = len([r for r in audit_reports if not r.is_acceptable])
    print(f"""
测试结果摘要:
  - 工作目录: {workspace_dir}
  - 原始素材: {len(raw_materials):,} 字符
  - Writer 输出: {len(writer_output):,} 字符
  - 履约后输出: {len(fulfilled_content):,} 字符
  - 资产审计失败数: {audit_fail_count}
  - 校验结果: {'通过' if result.is_valid else '失败'}
  - 问题数量: {len(result.issues)}

生成的文件:
  - writer_output.md: Writer 原始输出
  - fulfilled_output.md: 资产履约后的输出
  - generated_assets/: 生成的 SVG 文件
""")

    return state, fulfilled_content, result


if __name__ == "__main__":
    asyncio.run(run_e2e_test())


# ============================================================================
# Pytest 兼容接口
# ============================================================================

import pytest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_e2e_sota2_pipeline():
    """
    端到端测试入口（pytest 兼容）

    运行方式:
        pytest tests/test_e2e_sota2.py -v -m slow

    注意:
        此测试需要真实的 LLM API 调用，运行时间较长（1-5 分钟）
    """
    state, fulfilled_content, result = await run_e2e_test()

    # 基本断言
    assert state is not None, "State 不应为空"
    assert fulfilled_content is not None, "Fulfilled content 不应为空"
    assert len(fulfilled_content) > 100, "内容应该有足够长度"

    # 检查结果
    assert result is not None, "Validation result 不应为空"
    # 允许有警告，但不应有严重错误
    error_count = sum(
        1 for i in result.issues
        if hasattr(i, 'severity') and i.severity.value == 'error'
    )
    assert error_count == 0, f"不应有严重错误，但发现 {error_count} 个"


def test_e2e_import_check():
    """快速测试：验证所有导入正常"""
    from src.core.validators import MarkdownValidator

    # 验证可以实例化
    validator = MarkdownValidator()
    assert validator is not None
