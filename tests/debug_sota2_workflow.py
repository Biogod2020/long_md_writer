"""
SOTA 2.0 调试工作流

逐步运行并审核：
1. AssetIndexerAgent - 资产索引 (含 VLM 贴标)
2. WriterAgent - 全量上下文创作
3. AssetFulfillmentAgent - 资产履约
4. AssetCriticAgent - 资产审计
5. EditorialQAAgent - 全量语义审核
6. ScriptDecoratorAgent - 交互脚本注入

每一步都会输出详细的检查结果，确保 SOTA 级别质量。
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.types import (
    AgentState,
    Manifest,
    SectionInfo,
    AssetEntry,
    AssetSource,
)
from src.core.gemini_client import GeminiClient
from src.core.validators import MarkdownValidator
from src.core.persistence import ProfileManager, AssetService

from src.agents.asset_indexer_agent import AssetIndexerAgent
from src.agents.writer_agent import WriterAgent
from src.agents.asset_fulfillment_agent import AssetFulfillmentAgent
from src.agents.asset_critic_agent import AssetCriticAgent
from src.agents.editorial_qa_agent import EditorialQAAgent, extract_semantic_summary
from src.agents.script_decorator_agent import ScriptDecoratorAgent


# ============================================================================
# 配置
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
ASSETS_DIR = PROJECT_ROOT / "assets" / "images" / "candidates_ecg-medication-effects"

# 输入文件
PROMPT_FILE = INPUTS_DIR / "prompt.txt"
RAW_FILES = [
    INPUTS_DIR / "Cardiovascular_markdown.md",
    INPUTS_DIR / "ECG Pathology and Clinical Features.md",
    INPUTS_DIR / "ecg_qa.md",
    INPUTS_DIR / "从偶极子到心电图.html",
]


# ============================================================================
# 辅助函数
# ============================================================================

def print_header(title: str, char: str = "="):
    """打印带格式的标题"""
    line = char * 70
    print(f"\n{line}")
    print(f" {title}")
    print(f"{line}\n")


def print_section(title: str):
    """打印小节标题"""
    print(f"\n--- {title} ---\n")


def print_check(name: str, passed: bool, details: str = ""):
    """打印检查结果"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} | {name}")
    if details:
        print(f"         └─ {details}")


def print_warning(msg: str):
    """打印警告"""
    print(f"  ⚠️  WARNING: {msg}")


def print_info(msg: str):
    """打印信息"""
    print(f"  ℹ️  {msg}")


def load_raw_materials() -> str:
    """加载原始素材"""
    materials = []

    for file_path in RAW_FILES:
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            materials.append(f"# 📄 {file_path.name}\n\n{content}\n")
            print(f"  ✓ 加载 {file_path.name} ({len(content):,} 字符)")
        else:
            print(f"  ✗ 文件不存在: {file_path}")

    return "\n\n---\n\n".join(materials)


def load_user_prompt() -> str:
    """加载用户指令"""
    if PROMPT_FILE.exists():
        content = PROMPT_FILE.read_text(encoding="utf-8")
        print(f"  ✓ 加载 prompt.txt ({len(content)} 字符)")
        return content
    else:
        print(f"  ✗ prompt.txt 不存在")
        return ""


# ============================================================================
# 审核函数
# ============================================================================

def review_uar(state: AgentState) -> dict:
    """审核 UAR (资产注册表)"""
    results = {"passed": True, "checks": [], "warnings": []}

    uar = state.get_uar()
    if uar is None:
        results["passed"] = False
        results["checks"].append(("UAR 初始化", False, "UAR 为空"))
        return results

    asset_count = len(uar.assets)
    results["checks"].append(("UAR 初始化", True, f"{asset_count} 个资产"))

    # 检查资产质量分布
    by_source = {}
    by_quality = {}
    with_labels = 0

    for asset in uar.assets.values():
        src = asset.source.value
        by_source[src] = by_source.get(src, 0) + 1

        if asset.quality_level:
            q = asset.quality_level.value
            by_quality[q] = by_quality.get(q, 0) + 1

        if asset.semantic_label:
            with_labels += 1

    results["checks"].append(("来源分布", True, str(by_source)))
    results["checks"].append(("语义标签覆盖", with_labels == asset_count, f"{with_labels}/{asset_count}"))

    if with_labels < asset_count:
        results["warnings"].append(f"{asset_count - with_labels} 个资产缺少语义标签")

    return results


def review_writer_output(content: str, section_id: str) -> dict:
    """审核 Writer 输出"""
    results = {"passed": True, "checks": [], "warnings": []}

    # 基本长度检查
    word_count = len(content)
    results["checks"].append(("内容长度", word_count > 500, f"{word_count} 字符"))

    if word_count < 500:
        results["passed"] = False

    # 检查必要元素
    has_h1 = content.count("# ") > 0
    has_h2 = content.count("## ") > 0
    has_math = "$" in content
    has_figure = "<figure" in content.lower() or ":::visual" in content

    results["checks"].append(("H1 标题", has_h1, ""))
    results["checks"].append(("H2 子标题", has_h2, ""))
    results["checks"].append(("数学公式", has_math, "LaTeX 公式" if has_math else "无公式"))
    results["checks"].append(("图像引用", has_figure, "<figure> 或 :::visual"))

    # 检查 :::visual 指令格式
    import re
    visual_blocks = re.findall(r':::visual\s*\{([^}]+)\}', content)
    valid_visuals = 0
    for block in visual_blocks:
        try:
            json.loads("{" + block + "}")
            valid_visuals += 1
        except:
            results["warnings"].append(f":::visual 块 JSON 格式错误")

    if visual_blocks:
        results["checks"].append((":::visual 格式", valid_visuals == len(visual_blocks),
                                  f"{valid_visuals}/{len(visual_blocks)} 有效"))

    # 检查交叉引用
    refs = re.findall(r'\[REF:([^\]]+)\]', content)
    if refs:
        results["checks"].append(("交叉引用", True, f"{len(refs)} 个引用"))

    # Markdown 语法验证
    validator = MarkdownValidator()
    validation = validator.validate_all(content, namespace=section_id)

    error_count = sum(1 for i in validation.issues if i.severity.value == "error")
    warning_count = sum(1 for i in validation.issues if i.severity.value == "warning")

    results["checks"].append(("Markdown 语法", error_count == 0,
                              f"{error_count} 错误, {warning_count} 警告"))

    if error_count > 0:
        results["passed"] = False
        for issue in validation.issues:
            if issue.severity.value == "error":
                results["warnings"].append(f"[{issue.severity.value}] {issue.message[:60]}")

    return results


def review_fulfillment(content: str, assets_dir: Path) -> dict:
    """审核资产履约结果"""
    results = {"passed": True, "checks": [], "warnings": []}

    # 检查是否还有未履约的 :::visual
    import re
    remaining_visuals = len(re.findall(r':::visual\s*\{', content))
    results["checks"].append(("所有 :::visual 已履约", remaining_visuals == 0,
                              f"剩余 {remaining_visuals} 个"))

    if remaining_visuals > 0:
        results["passed"] = False
        results["warnings"].append(f"仍有 {remaining_visuals} 个 :::visual 未被履约")

    # 检查生成的 SVG 文件
    svg_files = list(assets_dir.glob("*.svg")) if assets_dir.exists() else []
    results["checks"].append(("SVG 文件生成", len(svg_files) > 0, f"{len(svg_files)} 个文件"))

    # 检查 <figure> 标签
    figures = re.findall(r'<figure[^>]*>(.*?)</figure>', content, re.DOTALL)
    valid_figures = 0
    for fig in figures:
        if "<img" in fig and "<figcaption" in fig:
            valid_figures += 1

    results["checks"].append(("Figure 结构完整", valid_figures == len(figures),
                              f"{valid_figures}/{len(figures)} 完整"))

    # 检查图片路径
    img_srcs = re.findall(r'<img[^>]*src="([^"]*)"', content)
    valid_paths = 0
    for src in img_srcs:
        if src.startswith("generated_assets/") or src.startswith("assets/"):
            valid_paths += 1
        elif src.startswith("http"):
            valid_paths += 1  # 网络图片也算有效

    results["checks"].append(("图片路径有效", valid_paths == len(img_srcs),
                              f"{valid_paths}/{len(img_srcs)} 有效"))

    return results


def review_editorial_qa(report) -> dict:
    """审核 Editorial QA 结果"""
    results = {"passed": report.passed, "checks": [], "warnings": []}

    results["checks"].append(("QA 审核通过", report.passed, report.summary))
    results["checks"].append(("资产数量", report.asset_count > 0, f"{report.asset_count} 个"))

    error_count = sum(1 for i in report.issues if i.severity.value == "error")
    warning_count = sum(1 for i in report.issues if i.severity.value == "warning")

    results["checks"].append(("错误数量", error_count == 0, f"{error_count} 个"))
    results["checks"].append(("警告数量", warning_count < 5, f"{warning_count} 个"))

    for issue in report.issues:
        if issue.severity.value == "error":
            results["warnings"].append(f"[ERROR] {issue.message[:60]}")
        elif issue.severity.value == "warning":
            results["warnings"].append(f"[WARN] {issue.message[:60]}")

    return results


# ============================================================================
# 主工作流
# ============================================================================

async def run_debug_workflow():
    """运行调试工作流"""
    print_header("SOTA 2.0 调试工作流", "█")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"项目根目录: {PROJECT_ROOT}")

    # 创建工作目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir = PROJECT_ROOT / "workspace_test" / f"debug_{timestamp}"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "md").mkdir(exist_ok=True)
    (workspace_dir / "generated_assets").mkdir(exist_ok=True)

    print(f"工作目录: {workspace_dir}")

    # 初始化 Profile 管理器
    profile_manager = ProfileManager(profiles_dir=workspace_dir / "profiles")
    profile = profile_manager.create_profile(
        project_title="ECG 导联教程调试",
        profile_id=f"debug-{timestamp}",
        tags=["debug", "sota2"]
    )

    all_passed = True

    # =========================================================================
    # Step 1: 加载输入
    # =========================================================================
    print_header("Step 1: 加载输入", "-")

    print_section("1.1 加载用户指令")
    user_prompt = load_user_prompt()
    print(f"\n  指令内容:\n  {user_prompt[:200]}...")

    print_section("1.2 加载原始素材")
    raw_materials = load_raw_materials()
    print(f"\n  总长度: {len(raw_materials):,} 字符")

    # 记录输入蓝图
    profile_manager.record_input_blueprint(
        raw_materials_path=str(INPUTS_DIR),
        raw_materials_content=raw_materials,
        user_prompt_path=str(PROMPT_FILE),
        user_prompt_content=user_prompt,
        assets_dir=str(ASSETS_DIR),
        asset_files=[f.name for f in ASSETS_DIR.glob("*") if f.is_file()]
    )

    # 创建初始状态
    state = AgentState(
        job_id=f"debug-{timestamp}",
        workspace_path=str(workspace_dir),
        raw_materials=raw_materials,
        project_brief=user_prompt
    )

    # =========================================================================
    # Step 2: 资产索引 (AssetIndexerAgent)
    # =========================================================================
    print_header("Step 2: 资产索引 (AssetIndexerAgent)", "-")

    indexer = AssetIndexerAgent(
        input_dir=str(ASSETS_DIR),
        skip_vision=False  # 使用 VLM 贴标
    )

    print_section("2.1 扫描资产目录")
    print(f"  目录: {ASSETS_DIR}")

    try:
        state = await indexer.run_async(state)  # 使用异步版本避免 asyncio.run() 嵌套

        print_section("2.2 资产索引结果审核")
        uar_review = review_uar(state)

        for check_name, passed, details in uar_review["checks"]:
            print_check(check_name, passed, details)

        for warning in uar_review["warnings"]:
            print_warning(warning)

        if not uar_review["passed"]:
            all_passed = False

        # 保存 UAR 检查点
        profile_manager.record_uar_checkpoint(state)

    except Exception as e:
        print(f"  ❌ 资产索引失败: {e}")
        all_passed = False

    # =========================================================================
    # Step 3: 创建 Manifest
    # =========================================================================
    print_header("Step 3: 创建 Manifest", "-")

    state.manifest = Manifest(
        project_title="心电图物理原理教程 - 第二章",
        description='从导线到导联——我们如何全方位"观"心',
        sections=[
            SectionInfo(
                id="sec-2-1",
                title="导联的基本概念",
                summary="""深入介绍心电导联的物理原理和临床应用，包括：
1. 电极与导联的本质区别
2. 标准双极肢体导联 (I, II, III) 的物理推导和爱因托芬三角
3. 加压单极肢体导联 (aVR, aVL, aVF) 与 Wilson 中心电端
4. 胸前导联 (V1-V6) 的解剖位置与观察视角
5. 六轴参考系统的构建与电轴判读
6. 导联系统如何帮助定位心肌病变""",
                estimated_words=5000,  # 增加到5000字
                metadata={"namespace": "s1", "visual_intent": "需要导联位置示意图、Einthoven三角图、六轴系统图、胸前导联解剖图"}
            ),
        ]
    )

    profile_manager.record_manifest(state.manifest)

    print_check("Manifest 创建", True, f"{len(state.manifest.sections)} 个章节")
    for sec in state.manifest.sections:
        print(f"    - {sec.id}: {sec.title} (~{sec.estimated_words} 字)")

    # =========================================================================
    # Step 4: Writer 创作 (支持多轮重写)
    # =========================================================================
    print_header("Step 4: Writer 创作 (WriterAgent)", "-")

    writer = WriterAgent()
    state.current_section_index = 0
    section = state.manifest.sections[0]
    min_word_count = section.estimated_words
    max_write_attempts = 3
    write_attempt = 0
    writer_output = ""

    while write_attempt < max_write_attempts:
        write_attempt += 1
        print_section(f"4.1 创作尝试 {write_attempt}/{max_write_attempts}")
        print("  (这可能需要 2-5 分钟...)")

        try:
            # 重置状态以便重写
            state.current_section_index = 0
            state.completed_md_sections = []

            state = await writer.run(state)

            # 获取输出
            md_path = workspace_dir / "md" / f"{section.id}.md"

            if md_path.exists():
                writer_output = md_path.read_text(encoding="utf-8")
            else:
                writer_output = state.completed_md_sections.get(section.id, "") if state.completed_md_sections else ""

            # 计算中文字数 (排除标点和空格)
            import re
            chinese_chars = re.findall(r'[\u4e00-\u9fff]', writer_output)
            char_count = len(chinese_chars)

            print_section("4.2 Writer 输出审核")
            print(f"  输出总长度: {len(writer_output):,} 字符")
            print(f"  中文字符数: {char_count:,} 字")
            print(f"  最低要求: {min_word_count:,} 字")

            # 字数检查
            word_count_passed = char_count >= min_word_count * 0.8  # 允许 80% 的容差
            print_check("字数检查", word_count_passed, f"{char_count}/{min_word_count} 字 ({char_count*100//min_word_count}%)")

            writer_review = review_writer_output(writer_output, "s1")

            for check_name, passed, details in writer_review["checks"]:
                print_check(check_name, passed, details)

            for warning in writer_review["warnings"]:
                print_warning(warning)

            if not writer_review["passed"]:
                all_passed = False

            # 如果字数不足且还有重试机会，触发重写
            if not word_count_passed and write_attempt < max_write_attempts:
                print_warning(f"字数不足 ({char_count}/{min_word_count})，触发重写...")
                state.rewrite_needed = True
                state.rewrite_feedback = f"""
## 字数不足，必须重写！

当前字数: {char_count} 字
最低要求: {min_word_count} 字
缺口: {min_word_count - char_count} 字

请在以下方面补充内容：
1. 每个物理概念增加详细的数学推导过程
2. 增加更多临床应用实例
3. 增加对比分析和知识扩展
4. 每个小节都需要有充分的解释和例证
"""
                continue
            else:
                break

        except Exception as e:
            print(f"  ❌ Writer 创作失败: {e}")
            import traceback
            traceback.print_exc()
            if write_attempt >= max_write_attempts:
                all_passed = False
                writer_output = ""
                break

    # 保存最终 Writer 输出
    if writer_output:
        writer_output_path = workspace_dir / "writer_output.md"
        writer_output_path.write_text(writer_output, encoding="utf-8")
        print_info(f"已保存到: {writer_output_path}")

        # 输出预览
        print_section("4.3 内容预览")
        preview = writer_output[:1000]
        print(f"```\n{preview}\n...\n```")

        profile_manager.record_completed_section(section.id, writer_output)

    # =========================================================================
    # Step 5: 资产履约 (AssetFulfillmentAgent)
    # =========================================================================
    if writer_output:
        print_header("Step 5: 资产履约 (AssetFulfillmentAgent)", "-")

        fulfillment = AssetFulfillmentAgent(
            skip_generation=False,
            skip_search=True
        )

        namespace = state.manifest.sections[0].metadata.get("namespace", "s1")

        print_section("5.1 开始履约")

        try:
            state, fulfilled_content = await fulfillment.run_async(
                state, writer_output, namespace
            )

            print_section("5.2 履约结果审核")
            print(f"  输出长度: {len(fulfilled_content):,} 字符")

            assets_dir = workspace_dir / "generated_assets"
            fulfillment_review = review_fulfillment(fulfilled_content, assets_dir)

            for check_name, passed, details in fulfillment_review["checks"]:
                print_check(check_name, passed, details)

            for warning in fulfillment_review["warnings"]:
                print_warning(warning)

            if not fulfillment_review["passed"]:
                all_passed = False

            # 保存履约输出
            fulfilled_path = workspace_dir / "fulfilled_output.md"
            fulfilled_path.write_text(fulfilled_content, encoding="utf-8")
            print_info(f"已保存到: {fulfilled_path}")

        except Exception as e:
            print(f"  ❌ 资产履约失败: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
            fulfilled_content = writer_output
    else:
        fulfilled_content = ""

    # =========================================================================
    # Step 5.5: 资产审计 (AssetCriticAgent) - 多轮审核循环
    # =========================================================================
    if fulfilled_content:
        print_header("Step 5.5: 资产审计 (AssetCriticAgent)", "-")

        critic = AssetCriticAgent(skip_audit=False)
        uar = state.asset_registry
        assets_dir = workspace_dir / "generated_assets"

        # 收集需要审核的资产
        assets_to_audit = []
        for asset_id, asset in uar.assets.items():
            if asset.source.value == "AI" and asset.local_path:
                intent = asset.semantic_label or asset.alt_text or "未知意图"
                assets_to_audit.append((asset, intent))

        print_section("5.5.1 收集待审核资产")
        print(f"  待审核资产: {len(assets_to_audit)} 个")
        for asset, intent in assets_to_audit:
            print(f"    - {asset.id}: {intent[:50]}...")

        if assets_to_audit:
            print_section("5.5.2 执行多轮审核")

            max_audit_rounds = 3
            audit_round = 0
            failed_assets = assets_to_audit.copy()
            all_audit_reports = []

            while failed_assets and audit_round < max_audit_rounds:
                audit_round += 1
                print(f"\n  🔄 审核轮次 {audit_round}/{max_audit_rounds}")

                current_failed = []
                for asset, intent in failed_assets:
                    try:
                        report = await critic.audit_asset_async(
                            asset, intent, workspace_path=workspace_dir
                        )
                        all_audit_reports.append(report)

                        if report.is_acceptable:
                            print(f"    ✅ {asset.id}: PASS (分数: {report.score:.2f})")
                        else:
                            print(f"    ❌ {asset.id}: {report.result.value} (分数: {report.score:.2f})")
                            for issue in report.issues[:2]:
                                print(f"       - {issue[:60]}...")
                            current_failed.append((asset, intent))

                            # 如果还有重试机会，尝试重新生成
                            if audit_round < max_audit_rounds:
                                print(f"    🔄 尝试重新生成 {asset.id}...")
                                # TODO: 调用 fulfillment agent 重新生成单个资产

                    except Exception as e:
                        print(f"    ⚠️  审核 {asset.id} 出错: {e}")
                        current_failed.append((asset, intent))

                failed_assets = current_failed
                if not failed_assets:
                    break

            print_section("5.5.3 审核结果汇总")
            passed_count = sum(1 for r in all_audit_reports if r.is_acceptable)
            total_count = len(all_audit_reports)
            print_check(
                "资产审核通过率",
                passed_count == total_count,
                f"{passed_count}/{total_count} 通过"
            )

            if failed_assets:
                print_warning(f"仍有 {len(failed_assets)} 个资产未通过审核")
                all_passed = False

            # 保存审核报告
            audit_reports_path = workspace_dir / "asset_audit_reports.json"
            audit_reports_path.write_text(
                json.dumps([r.to_dict() for r in all_audit_reports], indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print_info(f"审核报告已保存到: {audit_reports_path}")
        else:
            print("  没有 AI 生成的资产需要审核")

    # =========================================================================
    # Step 6: Editorial QA 审核
    # =========================================================================
    if fulfilled_content:
        print_header("Step 6: Editorial QA 审核", "-")

        editorial_qa = EditorialQAAgent(skip_llm_review=False)

        print_section("6.1 执行语义审核")

        try:
            state, qa_report = await editorial_qa.run_async(
                state, fulfilled_content, namespace
            )

            print_section("6.2 审核结果")
            qa_review = review_editorial_qa(qa_report)

            for check_name, passed, details in qa_review["checks"]:
                print_check(check_name, passed, details)

            for warning in qa_review["warnings"]:
                print_warning(warning)

            if not qa_review["passed"]:
                all_passed = False

            # 保存 QA 报告
            qa_report_path = workspace_dir / "qa_report.json"
            qa_report_path.write_text(
                json.dumps(qa_report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            print_info(f"QA 报告已保存到: {qa_report_path}")

        except Exception as e:
            print(f"  ❌ Editorial QA 失败: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    # =========================================================================
    # Step 7: 语义摘要提取
    # =========================================================================
    if fulfilled_content:
        print_header("Step 7: 语义摘要提取", "-")

        try:
            summary = await extract_semantic_summary(fulfilled_content)

            if summary:
                print_check("摘要提取", True, summary.title)
                print(f"  核心概念: {', '.join(summary.core_concepts[:5])}")
                print(f"  视觉资产: {len(summary.visual_assets)} 个")
                print(f"  摘要: {summary.summary[:100]}...")

                # 保存摘要
                summary_path = workspace_dir / "semantic_summary.json"
                summary_path.write_text(
                    json.dumps(summary.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            else:
                print_check("摘要提取", False, "返回空")

        except Exception as e:
            print(f"  ❌ 语义摘要提取失败: {e}")

    # =========================================================================
    # 最终报告
    # =========================================================================
    print_header("最终报告", "█")

    # 更新 Profile 状态
    if all_passed:
        profile_manager.mark_completed()
    else:
        profile_manager.mark_failed("部分检查未通过")

    profile_manager.save_profile()

    print(f"""
工作流完成状态: {'✅ 全部通过' if all_passed else '⚠️ 部分检查未通过'}

生成的文件:
  - writer_output.md       : Writer 原始输出
  - fulfilled_output.md    : 资产履约后的输出
  - qa_report.json         : Editorial QA 报告
  - semantic_summary.json  : 语义摘要
  - generated_assets/      : 生成的 SVG 文件
  - profiles/              : Profile 快照

工作目录: {workspace_dir}

下一步建议:
  1. 检查 fulfilled_output.md 的内容质量
  2. 查看 qa_report.json 中的问题详情
  3. 验证 generated_assets/ 中的 SVG 图形是否准确
""")

    return state, fulfilled_content, all_passed


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    asyncio.run(run_debug_workflow())
