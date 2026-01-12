"""
SOTA 2.0 自动化测试 (无人工审批)

运行完整 SOTA 2.0 流程，自动通过所有审批点。
用于快速测试整个工作流到 Markdown 生成阶段。
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, SectionInfo

# SOTA 2.0 Agents
from src.agents.asset_indexer_agent import AssetIndexerAgent
from src.agents.clarifier_agent import ClarifierAgent
from src.agents.refiner_agent import RefinerAgent
from src.agents.architect_agent import ArchitectAgent
from src.agents.techspec_agent import TechSpecAgent
from src.agents.writer_agent import WriterAgent
from src.agents.asset_fulfillment_agent import AssetFulfillmentAgent
from src.agents.asset_critic_agent import AssetCriticAgent
from src.agents.editorial_qa_agent import EditorialQAAgent


# ============================================================================
# 配置
# ============================================================================

INPUTS_DIR = Path(__file__).parent.parent / "inputs"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "images" / "candidates_ecg-medication-effects"


def load_inputs():
    """加载输入"""
    prompt = (INPUTS_DIR / "prompt.txt").read_text(encoding="utf-8")

    materials = []
    for f in ["Cardiovascular_markdown.md", "ECG Pathology and Clinical Features.md",
              "ecg_qa.md", "从偶极子到心电图.html"]:
        path = INPUTS_DIR / f
        if path.exists():
            materials.append(f"# {f}\n\n{path.read_text(encoding='utf-8')}")
            print(f"  ✓ {f}")

    return prompt, "\n\n---\n\n".join(materials)


async def run_sota2_auto():
    """自动运行 SOTA 2.0 完整流程"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"sota2_auto_{timestamp}"

    print("\n" + "=" * 70)
    print(f" SOTA 2.0 自动化测试 - {job_id}")
    print("=" * 70)

    # 创建工作目录
    workspace = Path("workspace") / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "md").mkdir(exist_ok=True)
    (workspace / "generated_assets").mkdir(exist_ok=True)
    print(f"📁 工作目录: {workspace}")

    # 加载输入
    print("\n--- 加载输入 ---")
    user_prompt, raw_materials = load_inputs()
    print(f"  总长度: {len(raw_materials):,} 字符")

    # 初始化状态
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace),
        raw_materials=f"# 用户需求\n\n{user_prompt}\n\n# 原始素材\n\n{raw_materials}",
        project_brief=user_prompt,
    )

    client = GeminiClient()

    # =========================================================================
    # Phase 0: Asset Indexing
    # =========================================================================
    print("\n" + "-" * 70)
    print("Phase 0: Asset Indexing (VLM 贴标)")
    print("-" * 70)

    indexer = AssetIndexerAgent(
        client=client,
        input_dir=str(ASSETS_DIR),
        skip_vision=False
    )
    state = await indexer.run_async(state)

    uar = state.asset_registry
    print(f"  ✓ 索引完成: {len(uar.assets)} 个资产")

    # =========================================================================
    # Phase 1: Clarifier → Refiner → Architect (自动)
    # =========================================================================
    print("\n" + "-" * 70)
    print("Phase 1: Clarifier → Refiner → Architect")
    print("-" * 70)

    # Clarifier (async)
    print("\n[1.1] Clarifier...")
    clarifier = ClarifierAgent(client)
    questions = await clarifier.run_async(state)
    state.clarifier_questions = questions
    print(f"  ✓ 生成 {len(questions)} 个澄清问题")

    # 自动回答 (使用合理默认值)
    auto_answers = {
        q.get('id', f'q{i}'): "采用与第一章一致的风格，保持学术严谨性，使用矢量图形，聚焦物理原理"
        for i, q in enumerate(questions)
    }
    state.clarifier_answers = auto_answers
    print(f"  ✓ 自动回答澄清问题")

    # Refiner (async)
    print("\n[1.2] Refiner...")
    refiner = RefinerAgent(client)
    brief = await refiner.run_async(state, clarification_answers=state.clarifier_answers)
    state.project_brief = brief
    state.brief_approved = True
    print(f"  ✓ 生成 Brief ({len(brief)} 字符)")

    # Architect (async)
    print("\n[1.3] Architect...")
    architect = ArchitectAgent(client)
    state = await architect.run_async(state)
    state.outline_approved = True

    if state.manifest:
        print(f"  ✓ Manifest: {state.manifest.project_title}")
        print(f"  ✓ 章节数: {len(state.manifest.sections)}")
        for sec in state.manifest.sections:
            print(f"    - {sec.id}: {sec.title} (~{sec.estimated_words} 字)")
    else:
        print("  ❌ Manifest 生成失败")
        return state

    # =========================================================================
    # Phase 2: TechSpec
    # =========================================================================
    print("\n" + "-" * 70)
    print("Phase 2: TechSpec")
    print("-" * 70)

    techspec = TechSpecAgent(client)
    state = await techspec.run_async(state)
    print("  ✓ TechSpec 完成")

    # =========================================================================
    # Phase 3: Writer + Fulfillment + Critic (循环)
    # =========================================================================
    print("\n" + "-" * 70)
    print("Phase 3: Writer → Fulfillment → Critic (循环)")
    print("-" * 70)

    writer = WriterAgent(client)
    fulfillment = AssetFulfillmentAgent(
        client=client,
        skip_generation=False,
        skip_search=True
    )
    critic = AssetCriticAgent(client=client, skip_audit=False)

    state.current_section_index = 0
    state.completed_md_sections = []

    while state.current_section_index < len(state.manifest.sections):
        section = state.manifest.sections[state.current_section_index]
        namespace = f"s{state.current_section_index + 1}"

        print(f"\n[3.{state.current_section_index + 1}] 写作章节: {section.id} - {section.title}")

        # Writer
        print("  [Writer] 创作中...")
        state = await writer.run(state)

        # 读取输出
        md_path = workspace / "md" / f"{section.id}.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8")
            print(f"  [Writer] ✓ 完成 ({len(content):,} 字符)")

            # Fulfillment
            print("  [Fulfillment] 履约资产...")
            state, fulfilled = await fulfillment.run_async(state, content, namespace)
            md_path.write_text(fulfilled, encoding="utf-8")
            print(f"  [Fulfillment] ✓ 完成")

            # Critic - 审核 AI 生成的资产
            print("  [Critic] 审计资产...")
            ai_assets = [
                (a, a.semantic_label or "")
                for a in uar.assets.values()
                if a.source.value == "AI" and namespace in (a.tags or [])
            ]
            if ai_assets:
                for asset, intent in ai_assets:
                    try:
                        report = await critic.audit_asset_async(asset, intent, workspace)
                        status = "✅" if report.is_acceptable else "⚠️"
                        print(f"    {status} {asset.id}: {report.result.value} ({report.score:.2f})")
                    except Exception as e:
                        print(f"    ⚠️ {asset.id}: {e}")
            else:
                print("    没有新资产需要审计")

            # Note: Writer already adds to completed_md_sections and increments index
            pass
        else:
            print(f"  [Writer] ❌ 文件未生成")
            # Only increment on failure - Writer handles success case
            state.current_section_index += 1

    # =========================================================================
    # Phase 4: Editorial QA
    # =========================================================================
    print("\n" + "-" * 70)
    print("Phase 4: Editorial QA")
    print("-" * 70)

    editorial = EditorialQAAgent(client=client, skip_llm_review=False)

    for md_path in state.completed_md_sections:
        p = Path(md_path)
        if p.exists():
            content = p.read_text(encoding="utf-8")
            section_name = p.stem
            namespace = section_name.replace("sec-", "s").replace("-", "")

            print(f"\n  审核 {section_name}...")
            state, report = await editorial.run_async(state, content, namespace)

            if report.passed:
                print(f"    ✅ 通过")
            else:
                print(f"    ⚠️ {len(report.issues)} 个问题:")
                for issue in report.issues[:3]:
                    print(f"      - [{issue.severity.value}] {issue.message[:60]}...")

    # =========================================================================
    # 最终报告
    # =========================================================================
    print("\n" + "=" * 70)
    print(" 完成!")
    print("=" * 70)

    print(f"\n📊 结果摘要:")
    print(f"  Job ID: {state.job_id}")
    print(f"  工作目录: {state.workspace_path}")

    if state.manifest:
        print(f"\n📚 Manifest: {state.manifest.project_title}")
        print(f"  章节数: {len(state.manifest.sections)}")

    print(f"\n📝 已完成 Markdown: {len(state.completed_md_sections)} 个")
    total_chars = 0
    for md_path in state.completed_md_sections:
        p = Path(md_path)
        if p.exists():
            chars = len(p.read_text(encoding="utf-8"))
            total_chars += chars
            print(f"    - {p.name}: {chars:,} 字符")
    print(f"  总字符数: {total_chars:,}")

    if state.asset_registry:
        print(f"\n🎨 资产:")
        by_source = {}
        for a in state.asset_registry.assets.values():
            s = a.source.value
            by_source[s] = by_source.get(s, 0) + 1
        for s, c in by_source.items():
            print(f"    - {s}: {c}")

    if state.errors:
        print(f"\n❌ 错误: {len(state.errors)}")
        for e in state.errors:
            print(f"    - {e}")

    # 列出生成的文件
    print(f"\n📁 生成的文件:")
    for f in sorted(workspace.rglob("*")):
        if f.is_file():
            print(f"    - {f.relative_to(workspace)}")

    return state


if __name__ == "__main__":
    asyncio.run(run_sota2_auto())
