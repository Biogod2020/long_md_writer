"""
SOTA 2.0 集成测试

使用用户提供的 ECG 材料测试完整流程：
- 用户指令: inputs/prompt.txt
- Raw materials: inputs/*.md, inputs/*.html
- 图像资产: assets/ 文件夹
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.types import (
    AgentState,
    Manifest,
    SectionInfo,
    AssetEntry,
    AssetSource,
    AssetQualityLevel,
)
from src.agents.asset_indexer_agent import AssetIndexerAgent
from src.agents.writer_agent import WriterAgent
from src.agents.asset_fulfillment_agent import AssetFulfillmentAgent
from src.agents.asset_critic_agent import AssetCriticAgent, AuditResult
from src.core.validators import MarkdownValidator


def load_raw_materials(base_path: Path) -> str:
    """加载原始素材"""
    materials = []

    # 加载文本材料
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
            print(f"  ✓ 加载 {filename} ({len(content)} 字符)")

    # 加载 HTML 材料
    html_file = base_path / "从偶极子到心电图.html"
    if html_file.exists():
        content = html_file.read_text(encoding="utf-8")
        materials.append(f"# 📄 从偶极子到心电图.html\n\n{content}\n")
        print(f"  ✓ 加载 从偶极子到心电图.html ({len(content)} 字符)")

    return "\n\n---\n\n".join(materials)


def load_user_prompt(base_path: Path) -> str:
    """加载用户指令"""
    prompt_file = base_path / "prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""


def test_asset_indexer():
    """测试资产索引器"""
    print("\n" + "=" * 60)
    print("测试 1: AssetIndexerAgent")
    print("=" * 60)

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state = AgentState(job_id="test-indexer", workspace_path=tmpdir)

        # 使用项目根目录的 assets 文件夹
        project_root = Path(__file__).parent.parent
        assets_dir = project_root / "assets" / "images"

        if not assets_dir.exists():
            print(f"  ⚠️ 资产目录不存在: {assets_dir}")
            print("  跳过资产索引测试")
            return

        # 创建索引器 (跳过 Vision API 调用)
        indexer = AssetIndexerAgent(
            input_dir=str(assets_dir),
            skip_vision=True  # 测试时跳过 Vision API
        )

        # 运行索引
        state = indexer.run(state)

        # 验证结果
        uar = state.asset_registry
        print(f"\n  注册的资产数量: {len(uar.assets)}")

        if uar.assets:
            print("\n  资产列表 (前 5 个):")
            for i, (asset_id, asset) in enumerate(list(uar.assets.items())[:5]):
                print(f"    - {asset_id}: {asset.semantic_label}")

        print("\n  ✓ AssetIndexerAgent 测试通过")
        return state


def test_writer_prompt_building():
    """测试 Writer 提示构建"""
    print("\n" + "=" * 60)
    print("测试 2: WriterAgent 提示构建")
    print("=" * 60)

    import tempfile
    project_root = Path(__file__).parent.parent
    inputs_dir = project_root / "inputs"

    with tempfile.TemporaryDirectory() as tmpdir:
        # 加载原始素材
        print("\n  加载原始素材...")
        raw_materials = load_raw_materials(inputs_dir)
        user_prompt = load_user_prompt(inputs_dir)

        print(f"\n  用户指令: {user_prompt[:100]}...")
        print(f"  原始素材总长度: {len(raw_materials)} 字符")

        # 创建状态
        state = AgentState(
            job_id="test-writer",
            workspace_path=tmpdir,
            raw_materials=raw_materials,
            project_brief=user_prompt
        )

        # 初始化 UAR 并添加模拟资产
        uar = state.initialize_uar()
        uar.register_batch([
            AssetEntry(
                id="u-ecg-pwave-demo",
                source=AssetSource.USER,
                semantic_label="心电图 P 波形态示意图",
                quality_level=AssetQualityLevel.HIGH,
                quality_notes="清晰的教学图示",
                suitable_for=["概念说明", "教学演示"],
                local_path="inputs/ecg_pwave.png",
                tags=["ecg", "p-wave", "cardiac"]
            ),
            AssetEntry(
                id="u-lead-placement",
                source=AssetSource.USER,
                semantic_label="12 导联电极放置位置图",
                quality_level=AssetQualityLevel.MEDIUM,
                quality_notes="分辨率一般",
                suitable_for=["位置说明"],
                unsuitable_for=["精确测量参考"],
                local_path="inputs/lead_placement.jpg",
                tags=["ecg", "leads", "electrode"]
            ),
        ])

        # 创建 Manifest
        state.manifest = Manifest(
            project_title="心电图物理原理教程 - 第二章",
            description='从导线到导联——我们如何全方位"观"心',
            sections=[
                SectionInfo(
                    id="sec-2-1",
                    title="导联的基本概念",
                    summary="介绍心电导联的基本概念，包括标准导联和加压导联的区别",
                    estimated_words=1500,
                    metadata={"namespace": "s1", "visual_intent": "需要导联位置示意图"}
                ),
                SectionInfo(
                    id="sec-2-2",
                    title="Einthoven 三角与导联系统",
                    summary="详细讲解 Einthoven 三角的形成原理和导联系统",
                    estimated_words=2000,
                    metadata={"namespace": "s2", "visual_intent": "需要三角向量图"}
                ),
            ]
        )

        # 构建提示
        writer = WriterAgent()
        prompt = writer._build_multimodal_prompt(
            state,
            state.manifest.sections[0],
            "s1"
        )

        # 验证
        print(f"\n  生成的提示长度: {len(prompt)} 字符")

        # 检查关键内容
        checks = [
            ("UAR 摘要", "可用资产注册表" in prompt),
            ("资产 ID", "u-ecg-pwave-demo" in prompt),
            ("质量等级", "HIGH" in prompt),
            ("命名空间", "s1" in prompt),
            ("章节任务", "sec-2-1" in prompt),
            ("原始素材", "原始素材参考" in prompt),
        ]

        print("\n  内容检查:")
        for name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"    {status} {name}")

        all_checks_passed = all(p for _, p in checks)
        if all_checks_passed:
            print("\n  ✓ WriterAgent 提示构建测试通过")
        else:
            print("\n  ✗ WriterAgent 提示构建测试失败")
        assert all_checks_passed, "WriterAgent prompt is missing required sections"

        # 打印提示预览
        print("\n  提示预览 (前 1000 字符):")
        print("-" * 40)
        print(prompt[:1000])
        print("-" * 40)

        return state


def test_markdown_validator():
    """测试 Markdown 校验器"""
    print("\n" + "=" * 60)
    print("测试 3: MarkdownValidator")
    print("=" * 60)

    validator = MarkdownValidator()

    # 测试用例 1: 正确的 Writer 输出
    good_content = '''
## 导联的基本概念

心电导联是记录心脏电活动的基本工具。在临床上，我们使用 12 导联系统来全面观察心脏的电活动。

:::important
**核心概念**: 导联本质上是从特定角度观察心脏电向量的"窗口"。
:::

### 标准肢体导联

<figure>
<img src="inputs/lead_placement.jpg" alt="12 导联电极放置位置图" style="object-position: 50% 50%; object-fit: cover; width: 100%" data-asset-id="u-lead-placement">
<figcaption>图 2.1: 标准 12 导联电极放置位置</figcaption>
</figure>

根据 Einthoven 的定义，标准肢体导联包括：

- **I 导联**: 左臂 (+) 与右臂 (-) 之间的电位差，公式为 $V_I = V_{LA} - V_{RA}$
- **II 导联**: 左腿 (+) 与右臂 (-) 之间的电位差
- **III 导联**: 左腿 (+) 与左臂 (-) 之间的电位差

:::visual {"id": "s1-fig-einthoven", "action": "GENERATE_SVG", "description": "Einthoven 三角示意图，展示三个标准导联的空间关系"}
需要一张清晰的 Einthoven 三角示意图，展示 I、II、III 导联的向量方向和相互关系。
:::

### 数学关系

根据 Kirchhoff 电压定律，三个标准导联之间存在以下关系：

$$V_{II} = V_I + V_{III}$$

这被称为 **Einthoven 定律**。
'''

    result = validator.validate_all(good_content, namespace="s1")
    print("\n  测试用例 1 (正确内容):")
    print(f"    is_valid: {result.is_valid}")
    print(f"    问题数量: {len(result.issues)}")
    assert result.is_valid, "Expected good_content to pass validation"

    # 测试用例 2: 有错误的内容
    bad_content = '''
## 测试章节

:::visual {id: "wrong-json", action: GENERATE_SVG}
这是一个 JSON 格式错误的指令
:::

数学公式错误: $E = mc^2

未闭合的指令块：
:::important
这个块没有闭合
'''

    result = validator.validate_all(bad_content, namespace="s1")
    print("\n  测试用例 2 (错误内容):")
    print(f"    is_valid: {result.is_valid}")
    print(f"    问题数量: {len(result.issues)}")
    assert not result.is_valid, "Expected bad_content to fail validation"
    for issue in result.issues[:3]:
        print(f"      - {issue.severity.value}: {issue.message[:50]}...")

    print("\n  ✓ MarkdownValidator 测试通过")


def test_asset_fulfillment_parsing():
    """测试 Phase D: AssetFulfillmentAgent 指令解析"""
    print("\n" + "=" * 60)
    print("测试 4: AssetFulfillmentAgent 指令解析")
    print("=" * 60)

    import tempfile

    # 模拟 Writer 输出，包含多种 :::visual 指令
    writer_output = '''
## 导联的基本概念

心电导联是记录心脏电活动的基本工具。

<figure>
<img src="inputs/lead_placement.jpg" alt="12 导联电极放置位置图" style="object-position: 50% 50%;">
<figcaption>图 2.1: 电极放置位置</figcaption>
</figure>

### Einthoven 三角

:::visual {"id": "s1-fig-einthoven", "action": "GENERATE_SVG", "description": "Einthoven 三角示意图，展示三个标准导联的空间关系"}
需要一张清晰的 Einthoven 三角示意图。
:::

### 导联向量

:::visual {"id": "s1-fig-vectors", "action": "GENERATE_MERMAID", "description": "心脏电向量投影流程图"}
展示心脏电向量如何投影到各个导联轴上。
:::

### 胸导联

:::visual {"id": "s1-fig-chest", "action": "SEARCH_WEB", "description": "胸导联 V1-V6 电极放置位置实拍图"}
需要一张真实的胸导联放置位置照片。
:::
'''

    with tempfile.TemporaryDirectory() as tmpdir:
        state = AgentState(job_id="test-fulfillment", workspace_path=tmpdir)
        state.initialize_uar()

        # 创建履约器 (跳过实际生成)
        agent = AssetFulfillmentAgent(
            skip_generation=True,
            skip_search=True
        )

        # 解析指令
        directives = agent._parse_visual_directives(writer_output)

        print(f"\n  解析到 {len(directives)} 个 :::visual 指令:")
        assert len(directives) == 3, f"Expected 3 directives, got {len(directives)}"

        for d in directives:
            print(f"    - {d.id}: {d.action.value}")
            print(f"      描述: {d.description[:50]}...")

        # 验证各指令的 action 类型
        from src.core.types import AssetFulfillmentAction

        assert directives[0].action == AssetFulfillmentAction.GENERATE_SVG
        assert directives[1].action == AssetFulfillmentAction.GENERATE_MERMAID
        assert directives[2].action == AssetFulfillmentAction.SEARCH_WEB

        print("\n  ✓ 指令解析测试通过")

        # 执行履约 (使用占位符)
        state, fulfilled_content = agent.run(state, writer_output, "s1")

        print(f"\n  履约后内容长度: {len(fulfilled_content)} 字符")

        # 验证占位符已插入
        assert "svg-placeholder" in fulfilled_content or "SVG 占位符" in fulfilled_content
        assert "mermaid-placeholder" in fulfilled_content or "mermaid" in fulfilled_content.lower()
        assert "web-image-placeholder" in fulfilled_content or "网络图片占位符" in fulfilled_content

        # 验证原始 :::visual 块已被替换
        assert ":::visual" not in fulfilled_content

        print("  ✓ 履约替换测试通过")


def test_asset_critic():
    """测试 Phase D: AssetCriticAgent 审计"""
    print("\n" + "=" * 60)
    print("测试 5: AssetCriticAgent 审计")
    print("=" * 60)

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个测试 SVG 文件
        svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
  <rect width="100%" height="100%" fill="#f0f0f0"/>
  <circle cx="200" cy="150" r="50" fill="#3498db"/>
  <text x="200" y="155" text-anchor="middle" fill="white">Test</text>
</svg>'''
        svg_path = Path(tmpdir) / "test_asset.svg"
        svg_path.write_text(svg_content)

        # 创建资产条目
        asset = AssetEntry(
            id="test-svg-001",
            source=AssetSource.AI,
            local_path=str(svg_path),
            semantic_label="测试 SVG 图形",
            quality_level=AssetQualityLevel.HIGH,
        )

        # 创建审计员 (跳过实际 API 调用)
        critic = AssetCriticAgent(skip_audit=True)

        # 执行审计
        report = critic.audit_asset(
            asset,
            intent_description="一个简单的蓝色圆形示意图",
            workspace_path=Path(tmpdir)
        )

        print("\n  审计结果:")
        print(f"    资产 ID: {report.asset_id}")
        print(f"    结果: {report.result.value}")
        print(f"    分数: {report.score:.0%}")
        print(f"    可接受: {report.is_acceptable}")

        # 验证测试模式下的行为
        assert report.result == AuditResult.PASS
        assert report.is_acceptable

        print("\n  ✓ AssetCriticAgent 测试通过")

        # 测试 SVG 语法检查
        print("\n  测试 SVG 语法检查...")

        # 有效 SVG
        valid_svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        issues = critic._check_svg_syntax(valid_svg)
        assert len(issues) == 0, f"Valid SVG should have no issues, got: {issues}"
        print("    ✓ 有效 SVG 通过检查")

        # 无效 SVG - 缺少闭合标签
        invalid_svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10">'
        issues = critic._check_svg_syntax(invalid_svg)
        assert len(issues) > 0, "Invalid SVG should have issues"
        print(f"    ✓ 无效 SVG 检测到问题: {issues[0]}")


def test_phase_d_integration():
    """测试 Phase D 完整流程"""
    print("\n" + "=" * 60)
    print("测试 6: Phase D 完整流程集成")
    print("=" * 60)

    import tempfile

    # 模拟完整的 Writer -> Fulfillment -> Critic 流程
    writer_output = '''
## 心脏电向量

心脏电向量是理解心电图的基础概念。

:::visual {"id": "s1-fig-vector", "action": "GENERATE_SVG", "description": "心脏电向量示意图，展示瞬时向量的方向和大小"}
绘制一个简化的心脏电向量图，标注向量的起点（心脏中心）和终点，用箭头表示方向。
:::

电向量的大小和方向随心动周期变化。
'''

    with tempfile.TemporaryDirectory() as tmpdir:
        state = AgentState(job_id="test-phase-d", workspace_path=tmpdir)
        state.initialize_uar()

        print("\n  步骤 1: 资产履约...")

        # 创建履约器
        fulfillment_agent = AssetFulfillmentAgent(
            skip_generation=True,  # 测试模式
            skip_search=True
        )

        # 执行履约
        state, fulfilled_content = fulfillment_agent.run(state, writer_output, "s1")

        assert ":::visual" not in fulfilled_content, "Visual directives should be replaced"
        print("    ✓ 履约完成")

        print("\n  步骤 2: 资产审计...")

        # 创建审计员
        critic = AssetCriticAgent(skip_audit=True)

        # 创建模拟资产进行审计
        mock_asset = AssetEntry(
            id="s1-fig-vector",
            source=AssetSource.AI,
            local_path="generated_assets/s1-fig-vector.svg",
            semantic_label="心脏电向量示意图",
            quality_level=AssetQualityLevel.HIGH,
        )

        report = critic.audit_asset(
            mock_asset,
            "心脏电向量示意图，展示瞬时向量的方向和大小",
            Path(tmpdir)
        )

        assert report.is_acceptable, "Asset should pass audit in test mode"
        print(f"    ✓ 审计通过 (分数: {report.score:.0%})")

        print("\n  步骤 3: 验证最终输出...")

        # 验证输出内容结构
        assert "心脏电向量" in fulfilled_content
        assert "svg-placeholder" in fulfilled_content or "SVG" in fulfilled_content

        print("    ✓ 输出结构正确")

        print("\n  ✓ Phase D 完整流程测试通过")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("SOTA 2.0 集成测试")
    print("=" * 60)

    # Phase A & B 测试
    # 测试 1: 资产索引器
    test_asset_indexer()

    # 测试 2: Writer 提示构建
    test_writer_prompt_building()

    # 测试 3: Markdown 校验器
    test_markdown_validator()

    # Phase D 测试
    # 测试 4: 资产履约指令解析
    test_asset_fulfillment_parsing()

    # 测试 5: 资产审计
    test_asset_critic()

    # 测试 6: Phase D 完整流程
    test_phase_d_integration()

    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
