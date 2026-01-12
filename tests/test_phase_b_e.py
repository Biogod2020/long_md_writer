"""
Phase B & E 集成测试

测试内容：
1. ScriptDecoratorAgent - :::script 协议注入与解析
2. EditorialQAAgent - 全量语义审核
3. SemanticSummary - 语义摘要提取
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.script_decorator_agent import (
    ScriptDecoratorAgent,
    ScriptDirective,
    AVAILABLE_CONTROLLERS,
    get_components_schema
)
from src.agents.editorial_qa_agent import (
    EditorialQAAgent,
    QAReport,
    QAIssue,
    QAIssueType,
    QASeverity,
    extract_semantic_summary
)


# ============================================================================
# 测试数据
# ============================================================================

SAMPLE_MARKDOWN = """# 导联的基本概念

在上一章中，我们建立了一个关键的物理模型：心脏在任何给定瞬间的电活动，都可以等效为一个宏观的**综合电偶极子向量** $\\vec{P}$。

## 电极与导联

:::important
**核心定义：**
*   **电极 (Electrode)**：物理实体。
*   **导联 (Lead)**：虚拟视角。
:::

<figure>
<img src="generated_assets/s1-fig-electrodes-vs-leads.svg" alt="电极与导联对比图" style="object-position: 50% 50%; object-fit: cover" data-asset-id="s1-fig-electrodes-vs-leads">
<figcaption>展示10个电极在人体上的分布与12个导联输出的对应关系</figcaption>
</figure>

## 爱因托芬三角形

1901 年，心电图之父威廉·爱因托芬提出了著名的**爱因托芬三角形**。

$$ V_I = \\Phi_{LA} - \\Phi_{RA} $$

:::tip
在临床看图时，如果你发现 $V_I + V_{III} \\neq V_{II}$，通常意味着电极贴错位置了。
:::

<figure>
<img src="generated_assets/s1-fig-einthoven-triangle.svg" alt="爱因托芬三角形物理模型图" style="object-position: 50% 50%; object-fit: cover" data-asset-id="s1-fig-einthoven-triangle">
<figcaption>爱因托芬三角形物理模型图</figcaption>
</figure>

在下一节 `[REF:sec-2-2]` 中，我们将深入探讨波形演变。
"""

SAMPLE_MARKDOWN_WITH_ISSUES = """# 测试文档

这是一个有问题的文档。

<img src="broken/path/image.png">

:::visual {"id": "unfulfilled", "action": "GENERATE_SVG", "description": "未履约的视觉指令"}
这是一个未履约的 :::visual 指令
:::

<figure>
<img src="test.jpg" style="object-position: 150% -20%">
</figure>
"""


# ============================================================================
# Phase B 测试：ScriptDecoratorAgent
# ============================================================================

def test_available_controllers():
    """测试可用的交互控制器定义"""
    print("\n" + "=" * 60)
    print("测试 1: 可用交互控制器")
    print("=" * 60)

    schema = get_components_schema()
    print(f"\n定义了 {len(schema)} 个交互控制器:")

    for name, info in schema.items():
        print(f"  - {name}: {info['description']}")
        print(f"    适用于: {', '.join(info['applicable_to'])}")

    assert len(schema) >= 5, "至少应该有 5 个控制器"
    assert "image-zoom" in schema
    assert "tooltip" in schema
    assert "collapsible" in schema
    print("\n✓ 控制器定义测试通过")


def test_script_directive_validation():
    """测试脚本指令验证"""
    print("\n" + "=" * 60)
    print("测试 2: 脚本指令验证")
    print("=" * 60)

    # 有效指令
    valid_directive = ScriptDirective(
        controller="image-zoom",
        target_selector="#fig-1",
        params={"zoom_level": 2.5, "transition": "ease-out"}
    )
    is_valid, error = valid_directive.validate()
    print(f"\n有效指令验证: {is_valid} (错误: {error})")
    assert is_valid, f"应该有效: {error}"

    # 无效控制器
    invalid_controller = ScriptDirective(
        controller="unknown-controller",
        target_selector="#fig-1",
        params={}
    )
    is_valid, error = invalid_controller.validate()
    print(f"无效控制器验证: {is_valid} (错误: {error})")
    assert not is_valid, "应该无效"
    assert "未知" in error

    # 缺少必填参数
    missing_required = ScriptDirective(
        controller="tooltip",
        target_selector="#term-1",
        params={}  # 缺少 content
    )
    is_valid, error = missing_required.validate()
    print(f"缺少必填参数验证: {is_valid} (错误: {error})")
    assert not is_valid, "应该无效"
    assert "必填" in error

    # 无效枚举值
    invalid_enum = ScriptDirective(
        controller="tooltip",
        target_selector="#term-1",
        params={"content": "测试", "position": "invalid"}
    )
    is_valid, error = invalid_enum.validate()
    print(f"无效枚举值验证: {is_valid} (错误: {error})")
    assert not is_valid, "应该无效"
    assert "允许范围" in error

    print("\n✓ 指令验证测试通过")


def test_script_directive_to_markdown():
    """测试脚本指令转 Markdown"""
    print("\n" + "=" * 60)
    print("测试 3: 脚本指令转 Markdown")
    print("=" * 60)

    directive = ScriptDirective(
        controller="image-zoom",
        target_selector="#fig-einthoven",
        params={"zoom_level": 2.0}
    )

    md = directive.to_markdown()
    print(f"\n生成的 Markdown:\n{md}")

    assert ":::script" in md
    assert '"controller": "image-zoom"' in md
    assert '"target": "#fig-einthoven"' in md
    assert '"zoom_level": 2.0' in md
    assert ":::" in md

    print("\n✓ Markdown 生成测试通过")


def test_parse_existing_scripts():
    """测试解析已有的脚本块"""
    print("\n" + "=" * 60)
    print("测试 4: 解析已有脚本块")
    print("=" * 60)

    content_with_scripts = """# 测试文档

一些内容...

:::script {"controller": "image-zoom", "target": "#fig-1", "zoom_level": 2.5}
:::

更多内容...

:::script {"controller": "tooltip", "target": ".term", "content": "术语解释", "position": "top"}
:::
"""

    agent = ScriptDecoratorAgent(skip_analysis=True)
    directives = agent.parse_existing_scripts(content_with_scripts)

    print(f"\n解析到 {len(directives)} 个脚本指令:")
    for d in directives:
        print(f"  - {d.controller} -> {d.target_selector}")
        print(f"    参数: {d.params}")

    assert len(directives) == 2
    assert directives[0].controller == "image-zoom"
    assert directives[1].controller == "tooltip"

    print("\n✓ 脚本解析测试通过")


def test_validate_all_scripts():
    """测试批量验证脚本"""
    print("\n" + "=" * 60)
    print("测试 5: 批量验证脚本")
    print("=" * 60)

    # 有效内容
    valid_content = """
:::script {"controller": "image-zoom", "target": "#fig-1", "zoom_level": 2.0}
:::
:::script {"controller": "collapsible", "target": ".details", "default_open": false}
:::
"""

    agent = ScriptDecoratorAgent(skip_analysis=True)
    is_valid, errors = agent.validate_all_scripts(valid_content)
    print(f"\n有效内容验证: {is_valid} (错误数: {len(errors)})")
    assert is_valid, f"应该有效: {errors}"

    # 无效内容
    invalid_content = """
:::script {"controller": "unknown", "target": "#fig-1"}
:::
:::script {"controller": "tooltip", "target": ".term"}
:::
"""

    is_valid, errors = agent.validate_all_scripts(invalid_content)
    print(f"无效内容验证: {is_valid} (错误数: {len(errors)})")
    for err in errors:
        print(f"  - {err}")
    assert not is_valid
    assert len(errors) == 2

    print("\n✓ 批量验证测试通过")


async def test_script_decorator_run():
    """测试脚本装饰器运行（跳过 LLM）"""
    print("\n" + "=" * 60)
    print("测试 6: 脚本装饰器运行（跳过 LLM）")
    print("=" * 60)

    state = AgentState(
        job_id="test-script",
        workspace_path="/tmp/test",
        raw_materials="",
        project_brief=""
    )

    agent = ScriptDecoratorAgent(skip_analysis=True)
    state, decorated = await agent.run_async(state, SAMPLE_MARKDOWN, "s1")

    print(f"\n输入长度: {len(SAMPLE_MARKDOWN)}")
    print(f"输出长度: {len(decorated)}")

    # 跳过分析时，内容应该不变
    assert decorated == SAMPLE_MARKDOWN

    print("\n✓ 脚本装饰器运行测试通过")


# ============================================================================
# Phase E 测试：EditorialQAAgent
# ============================================================================

def test_qa_local_checks_clean():
    """测试本地检查 - 干净内容"""
    print("\n" + "=" * 60)
    print("测试 7: QA 本地检查 - 干净内容")
    print("=" * 60)

    state = AgentState(
        job_id="test-qa",
        workspace_path="/tmp/test",
        raw_materials="",
        project_brief=""
    )

    agent = EditorialQAAgent(skip_llm_review=True, strict_mode=False)
    state, report = agent.run(state, SAMPLE_MARKDOWN, "s1")

    print(f"\n审核结果: {'通过' if report.passed else '未通过'}")
    print(f"问题数量: {len(report.issues)}")
    print(f"资产数量: {report.asset_count}")
    print(f"摘要: {report.summary}")

    if report.issues:
        print("\n问题列表:")
        for issue in report.issues:
            print(f"  - [{issue.severity.value}] {issue.issue_type.value}: {issue.message}")

    # 干净内容应该没有 ERROR 级别的问题
    error_count = sum(1 for i in report.issues if i.severity == QASeverity.ERROR)
    assert error_count == 0, f"不应该有错误: {[i.message for i in report.issues if i.severity == QASeverity.ERROR]}"

    print("\n✓ 干净内容 QA 测试通过")


def test_qa_local_checks_issues():
    """测试本地检查 - 有问题内容"""
    print("\n" + "=" * 60)
    print("测试 8: QA 本地检查 - 有问题内容")
    print("=" * 60)

    state = AgentState(
        job_id="test-qa-issues",
        workspace_path="/tmp/test",
        raw_materials="",
        project_brief=""
    )

    agent = EditorialQAAgent(skip_llm_review=True, strict_mode=False)
    state, report = agent.run(state, SAMPLE_MARKDOWN_WITH_ISSUES, "s1")

    print(f"\n审核结果: {'通过' if report.passed else '未通过'}")
    print(f"问题数量: {len(report.issues)}")

    print("\n问题列表:")
    for issue in report.issues:
        print(f"  - [{issue.severity.value}] {issue.issue_type.value}")
        print(f"    {issue.message}")
        if issue.suggestion:
            print(f"    建议: {issue.suggestion}")

    # 应该检测到问题
    assert len(report.issues) > 0, "应该检测到问题"

    # 检查是否检测到未履约的 visual
    visual_issues = [i for i in report.issues if i.issue_type == QAIssueType.BROKEN_REFERENCE]
    assert len(visual_issues) > 0, "应该检测到未履约的 visual"

    # 检查是否检测到缺少 alt
    alt_issues = [i for i in report.issues if i.issue_type == QAIssueType.MISSING_ALT]
    assert len(alt_issues) > 0, "应该检测到缺少 alt"

    # 检查是否检测到 object-position 超范围
    crop_issues = [i for i in report.issues if i.issue_type == QAIssueType.CROP_MISMATCH]
    assert len(crop_issues) > 0, "应该检测到裁切范围错误"

    print("\n✓ 问题内容 QA 测试通过")


def test_qa_report_serialization():
    """测试 QA 报告序列化"""
    print("\n" + "=" * 60)
    print("测试 9: QA 报告序列化")
    print("=" * 60)

    report = QAReport(
        passed=False,
        issues=[
            QAIssue(
                issue_type=QAIssueType.MISSING_ALT,
                severity=QASeverity.WARNING,
                location="位置 100",
                message="缺少 alt 属性",
                suggestion="添加描述性 alt"
            )
        ],
        summary="测试摘要",
        asset_count=5,
        reviewed_count=5
    )

    data = report.to_dict()
    print(f"\n序列化结果:")
    import json
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert data["passed"] == False
    assert len(data["issues"]) == 1
    assert data["issues"][0]["type"] == "missing_alt"
    assert data["issues"][0]["severity"] == "warning"

    print("\n✓ 报告序列化测试通过")


async def test_semantic_summary_extraction():
    """测试语义摘要提取（跳过 LLM）"""
    print("\n" + "=" * 60)
    print("测试 10: 语义摘要提取")
    print("=" * 60)

    # 这个测试只验证函数可调用，不实际调用 LLM
    print("\n语义摘要提取函数已定义")
    print("  - extract_semantic_summary(content, client)")
    print("  - 返回 SemanticSummary 对象")
    print("  - 包含: title, core_concepts, key_terms, visual_assets, dependencies, summary")

    from src.agents.editorial_qa_agent import SemanticSummary, save_semantic_summary

    # 创建模拟摘要
    summary = SemanticSummary(
        title="导联的基本概念",
        core_concepts=["电极", "导联", "爱因托芬三角形", "威尔逊中心电端"],
        key_terms=[
            {"term": "电极", "definition": "贴在皮肤上的导电介质"},
            {"term": "导联", "definition": "通过代数运算得到的电压差"}
        ],
        visual_assets=[
            {"id": "s1-fig-electrodes-vs-leads", "purpose": "展示电极与导联的对应关系"},
            {"id": "s1-fig-einthoven-triangle", "purpose": "展示爱因托芬三角形物理模型"}
        ],
        dependencies=["第一章：心脏电偶极子模型"],
        summary="本节介绍心电导联的基本概念..."
    )

    data = summary.to_dict()
    print(f"\n模拟摘要序列化:")
    import json
    print(json.dumps(data, indent=2, ensure_ascii=False))

    assert data["title"] == "导联的基本概念"
    assert len(data["core_concepts"]) == 4
    assert len(data["visual_assets"]) == 2

    print("\n✓ 语义摘要测试通过")


# ============================================================================
# 主函数
# ============================================================================

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("Phase B & E 集成测试")
    print("=" * 70)

    # Phase B 测试
    print("\n" + "#" * 70)
    print("# Phase B: ScriptDecoratorAgent 测试")
    print("#" * 70)

    test_available_controllers()
    test_script_directive_validation()
    test_script_directive_to_markdown()
    test_parse_existing_scripts()
    test_validate_all_scripts()
    await test_script_decorator_run()

    # Phase E 测试
    print("\n" + "#" * 70)
    print("# Phase E: EditorialQAAgent 测试")
    print("#" * 70)

    test_qa_local_checks_clean()
    test_qa_local_checks_issues()
    test_qa_report_serialization()
    await test_semantic_summary_extraction()

    # 总结
    print("\n" + "=" * 70)
    print("所有测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
