"""
SOTA 2.0 完整工作流

整合所有 SOTA 2.0 功能：
- Phase 0: AssetIndexer (资产索引 + VLM 贴标)
- Phase 1: Clarifier → Refiner → Architect (需求澄清与规划)
- Phase 2: TechSpec (技术规格)
- Phase 3: Writer (循环) + AssetFulfillment + AssetCritic (内容创作与资产履约)
- Phase 4: EditorialQA / MarkdownQA (全量语义审核)

支持多轮审核循环和人工中断点。
"""

import uuid
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState, AssetSource

# SOTA 2.0 Agents
from ..agents.asset_management import AssetIndexerAgent, AssetFulfillmentAgent, AssetCriticAgent
from ..agents.clarifier_agent import ClarifierAgent
from ..agents.refiner_agent import RefinerAgent
from ..agents.architect_agent import ArchitectAgent
from ..agents.techspec_agent import TechSpecAgent
from ..agents.writer_agent import WriterAgent
from ..agents.editorial_qa_agent import EditorialQAAgent
from ..agents.markdown_qa_agent import MarkdownQAAgent


class SOTA2NodeFactory:
    """
    SOTA 2.0 节点工厂
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        assets_input_dir: str = "inputs",
        skip_vision: bool = False,
        skip_asset_audit: bool = False,
    ):
        self.client = client or GeminiClient()
        self.assets_input_dir = assets_input_dir
        self.skip_vision = skip_vision
        self.skip_asset_audit = skip_asset_audit

        # Initialize agents
        self.asset_indexer = AssetIndexerAgent(
            client=self.client,
            input_dir=assets_input_dir,
            skip_vision=skip_vision
        )
        self.clarifier = ClarifierAgent(self.client)
        self.refiner = RefinerAgent(self.client)
        self.architect = ArchitectAgent(self.client)
        self.techspec = TechSpecAgent(self.client)
        self.writer = WriterAgent(self.client)
        self.fulfillment = AssetFulfillmentAgent(
            client=self.client,
            skip_generation=False,
            skip_search=True
        )
        self.critic = AssetCriticAgent(
            client=self.client,
            skip_audit=skip_asset_audit
        )
        self.editorial_qa = EditorialQAAgent(
            client=self.client,
            skip_llm_review=False
        )
        self.markdown_qa = MarkdownQAAgent(self.client)

    # ================== Phase 0: Asset Indexing ==================

    async def asset_indexer_node(self, state: AgentState) -> AgentState:
        """资产索引节点 - VLM 贴标"""
        print("\n[SOTA2] 📦 Phase 0: Asset Indexing")
        state = await self.asset_indexer.run_async(state)

        uar = state.asset_registry
        if uar:
            print(f"  ✓ 已索引 {len(uar.assets)} 个资产")
        return state

    # ================== Phase 1: Planning ==================

    def clarifier_node(self, state: AgentState) -> AgentState:
        """澄清节点"""
        print("\n[SOTA2] 💡 Phase 1.1: Clarifier")
        questions = self.clarifier.run(state)
        state.clarifier_questions = questions
        print(f"  ✓ 生成 {len(questions)} 个澄清问题")
        return state

    def refiner_node(self, state: AgentState) -> AgentState:
        """精炼节点"""
        print("\n[SOTA2] 📝 Phase 1.2: Refiner")
        brief = self.refiner.run(
            state,
            clarification_answers=state.clarifier_answers,
            feedback=state.user_brief_feedback
        )
        state.project_brief = brief
        state.user_brief_feedback = None
        print(f"  ✓ 生成 Project Brief ({len(brief)} 字符)")
        return state

    def review_brief_node(self, state: AgentState) -> AgentState:
        """Brief 审核节点 (中断点)"""
        return state

    def architect_node(self, state: AgentState) -> AgentState:
        """架构节点 - 生成 Manifest"""
        print("\n[SOTA2] 🏗️ Phase 1.3: Architect")
        feedback = getattr(state, 'user_outline_feedback', None)
        state = self.architect.run(state, feedback=feedback)
        if hasattr(state, 'user_outline_feedback'):
            state.user_outline_feedback = None

        if state.manifest:
            print(f"  ✓ 生成 Manifest: {state.manifest.project_title}")
            print(f"  ✓ 章节数量: {len(state.manifest.sections)}")
            for sec in state.manifest.sections:
                print(f"    - {sec.id}: {sec.title} (~{sec.estimated_words} 字)")
        return state

    def review_outline_node(self, state: AgentState) -> AgentState:
        """大纲审核节点 (中断点)"""
        return state

    # ================== Phase 2: TechSpec ==================

    def techspec_node(self, state: AgentState) -> AgentState:
        """技术规格节点"""
        print("\n[SOTA2] 🔧 Phase 2: TechSpec")
        return self.techspec.run(state)

    # ================== Phase 3: Writing + Fulfillment + Critic ==================

    async def writer_node(self, state: AgentState) -> AgentState:
        """写手节点 - 写一个章节"""
        section_idx = state.current_section_index
        if state.manifest and section_idx < len(state.manifest.sections):
            section = state.manifest.sections[section_idx]
            print(f"\n[SOTA2] ✍️ Phase 3.1: Writer - {section.id}: {section.title}")
        return await self.writer.run(state)

    async def fulfillment_node(self, state: AgentState) -> AgentState:
        """资产履约节点 - 处理 :::visual 指令"""
        print("\n[SOTA2] 🎨 Phase 3.2: Asset Fulfillment")

        # 获取最新写完的章节
        if not state.completed_md_sections:
            return state

        latest_md_path = state.completed_md_sections[-1]
        md_content = Path(latest_md_path).read_text(encoding="utf-8")

        # 确定 namespace
        section_idx = state.current_section_index - 1  # Writer 已经 +1 了
        namespace = f"s{section_idx + 1}"

        # 执行履约
        state, fulfilled_content = await self.fulfillment.run_async(
            state, md_content, namespace
        )

        # 保存履约后的内容
        Path(latest_md_path).write_text(fulfilled_content, encoding="utf-8")
        print(f"  ✓ 履约完成，更新 {Path(latest_md_path).name}")

        return state

    async def critic_node(self, state: AgentState) -> AgentState:
        """资产审计节点 - 审核生成的资产"""
        print("\n[SOTA2] 🔍 Phase 3.3: Asset Critic")

        if self.skip_asset_audit:
            print("  ⏭️ 跳过资产审计")
            return state

        uar = state.asset_registry
        if not uar:
            return state

        workspace_path = Path(state.workspace_path)

        # 收集 AI 生成的资产
        ai_assets = [
            (asset, asset.semantic_label or asset.alt_text or "")
            for asset in uar.assets.values()
            if asset.source == AssetSource.AI
        ]

        if not ai_assets:
            print("  没有 AI 生成的资产需要审计")
            return state

        print(f"  待审计资产: {len(ai_assets)} 个")

        # 审计每个资产
        failed_count = 0
        for asset, intent in ai_assets:
            try:
                report = await self.critic.audit_asset_async(
                    asset, intent, workspace_path
                )
                if report.is_acceptable:
                    print(f"    ✅ {asset.id}: PASS (分数: {report.score:.2f})")
                else:
                    print(f"    ❌ {asset.id}: {report.result.value} (分数: {report.score:.2f})")
                    failed_count += 1
                    # TODO: 触发重新生成
            except Exception as e:
                print(f"    ⚠️ {asset.id}: 审计出错 - {e}")

        if failed_count > 0:
            state.errors.append(f"资产审计: {failed_count} 个资产未通过")

        return state

    # ================== Phase 4: QA ==================

    async def editorial_qa_node(self, state: AgentState) -> AgentState:
        """全量语义审核节点"""
        print("\n[SOTA2] 📋 Phase 4: Editorial QA")

        if not state.completed_md_sections:
            return state

        # 审核所有已完成章节
        for md_path in state.completed_md_sections:
            content = Path(md_path).read_text(encoding="utf-8")
            section_name = Path(md_path).stem
            namespace = section_name.replace("sec-", "s").replace("-", "")

            state, qa_report, updated_content = await self.editorial_qa.run_async(
                state, content, namespace
            )
            # 将修复后的内容写回文件
            if updated_content != content:
                Path(md_path).write_text(updated_content, encoding="utf-8")

            if qa_report.passed:
                print(f"    ✅ {section_name}: 审核通过")
            else:
                print(f"    ⚠️ {section_name}: {len(qa_report.issues)} 个问题")

        return state

    async def markdown_qa_node(self, state: AgentState) -> AgentState:
        """Markdown 质检节点"""
        return await self.markdown_qa.run(state)

    def markdown_review_node(self, state: AgentState) -> AgentState:
        """Markdown 人工审核节点 (中断点)"""
        return state


def create_sota2_workflow(
    client: Optional[GeminiClient] = None,
    assets_input_dir: str = "inputs",
    skip_vision: bool = False,
    skip_asset_audit: bool = False,
) -> StateGraph:
    """
    创建 SOTA 2.0 工作流

    完整流程:
    AssetIndexer → Clarifier → Refiner → Architect → TechSpec
    → Writer(循环) → Fulfillment → Critic → EditorialQA → MarkdownQA
    """

    nodes = SOTA2NodeFactory(
        client=client,
        assets_input_dir=assets_input_dir,
        skip_vision=skip_vision,
        skip_asset_audit=skip_asset_audit,
    )

    workflow = StateGraph(AgentState)

    # ============ 添加节点 ============ 

    # Phase 0: Asset Indexing
    workflow.add_node("asset_indexer", nodes.asset_indexer_node)

    # Phase 1: Planning
    workflow.add_node("clarifier", nodes.clarifier_node)
    workflow.add_node("refiner", nodes.refiner_node)
    workflow.add_node("review_brief", nodes.review_brief_node)
    workflow.add_node("architect", nodes.architect_node)
    workflow.add_node("review_outline", nodes.review_outline_node)

    # Phase 2: TechSpec
    workflow.add_node("techspec", nodes.techspec_node)

    # Phase 3: Writing + Fulfillment + Critic
    workflow.add_node("writer", nodes.writer_node)
    workflow.add_node("fulfillment", nodes.fulfillment_node)
    workflow.add_node("critic", nodes.critic_node)

    # Phase 4: QA
    workflow.add_node("editorial_qa", nodes.editorial_qa_node)
    workflow.add_node("markdown_qa", nodes.markdown_qa_node)
    workflow.add_node("markdown_review", nodes.markdown_review_node)

    # ============ 条件边函数 ============ 

    def should_review_brief(state: AgentState) -> Literal["architect", "refiner"]:
        if getattr(state, "brief_approved", False):
            return "architect"
        return "refiner"

    def should_review_outline(state: AgentState) -> Literal["techspec", "architect"]:
        if getattr(state, "outline_approved", False):
            return "techspec"
        return "architect"

    def should_continue_writing(state: AgentState) -> Literal["writer", "fulfillment"]:
        """判断是否继续写作 - 每个章节写完后都要经过 Fulfillment"""
        # 每个章节写完后都必须经过 Fulfillment 处理 :::visual 指令
        # should_continue_section_loop 会决定是否继续写下一章
        return "fulfillment"

    def should_continue_section_loop(state: AgentState) -> Literal["writer", "editorial_qa"]:
        """判断是否继续章节循环 (Writer → Fulfillment → Critic)"""
        if state.all_sections_written():
            return "editorial_qa"
        return "writer"

    def should_run_md_qa_loop(state: AgentState) -> Literal["markdown_qa", "markdown_review"]:
        if state.md_qa_needs_revision and state.md_qa_iterations < 3:
            return "markdown_qa"
        return "markdown_review"

    def should_approve_markdown(state: AgentState) -> Literal["markdown_qa", "end"]:
        if getattr(state, "markdown_approved", False):
            return "end"
        return "markdown_qa"

    # ============ 添加边 ============ 

    # 入口: Asset Indexer
    workflow.set_entry_point("asset_indexer")

    # Phase 0 → Phase 1
    workflow.add_edge("asset_indexer", "clarifier")

    # Phase 1: Planning loop
    workflow.add_edge("clarifier", "refiner")
    workflow.add_edge("refiner", "review_brief")
    workflow.add_conditional_edges(
        "review_brief",
        should_review_brief,
        {"architect": "architect", "refiner": "refiner"}
    )
    workflow.add_edge("architect", "review_outline")
    workflow.add_conditional_edges(
        "review_outline",
        should_review_outline,
        {"techspec": "techspec", "architect": "architect"}
    )

    # Phase 2 → Phase 3
    workflow.add_edge("techspec", "writer")

    # Phase 3: Writing loop (Writer → Fulfillment → Critic → 下一章节或QA)
    workflow.add_conditional_edges(
        "writer",
        should_continue_writing,
        {"writer": "writer", "fulfillment": "fulfillment"}
    )
    workflow.add_edge("fulfillment", "critic")
    workflow.add_conditional_edges(
        "critic",
        should_continue_section_loop,
        {"writer": "writer", "editorial_qa": "editorial_qa"}
    )

    # Phase 4: QA loop
    workflow.add_edge("editorial_qa", "markdown_qa")
    workflow.add_conditional_edges(
        "markdown_qa",
        should_run_md_qa_loop,
        {"markdown_qa": "markdown_qa", "markdown_review": "markdown_review"}
    )
    workflow.add_conditional_edges(
        "markdown_review",
        should_approve_markdown,
        {"markdown_qa": "markdown_qa", "end": END}
    )

    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["refiner", "review_brief", "review_outline", "markdown_review"]
    )


async def run_sota2_workflow(
    user_intent: str,
    reference_materials: str = "",
    assets_input_dir: str = "inputs",
    workspace_base: str = "./workspace",
    job_id: Optional[str] = None,
    skip_vision: bool = False,
    skip_asset_audit: bool = False,
    debug_mode: bool = False,
    global_uar_path: Optional[str] = None,
) -> AgentState:
    """
    运行 SOTA 2.0 完整工作流

    Args:
        user_intent: 用户意图/指令 (告诉 AI 做什么)
        reference_materials: 参考资料全文 (知识/数据，供创作参考)
        assets_input_dir: 资产输入目录
        workspace_base: 工作目录基础路径
        job_id: 任务 ID
        skip_vision: 跳过 VLM 贴标
        skip_asset_audit: 跳过资产审计
        debug_mode: 调试模式
        global_uar_path: 全局 UAR 路径 (用于跨项目资产复用)
    """
    # 生成 job_id
    if not job_id:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_id = f"sota2_{timestamp}"

    # 创建工作目录
    workspace_path = Path(workspace_base) / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "md").mkdir(exist_ok=True)
    (workspace_path / "generated_assets").mkdir(exist_ok=True)

    print(f"\n{'='*70}")
    print(f" SOTA 2.0 Workflow - {job_id}")
    print(f"{'='*70}")
    print(f"📁 工作目录: {workspace_path}")
    if global_uar_path:
        print(f"🔗 全局资产库: {global_uar_path}")

    # 初始化状态 (SOTA 2.0: 严格分离 user_intent 与 reference_materials)
    initial_state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent=user_intent,
        reference_materials=reference_materials,
        debug_mode=debug_mode,
        uar_path=global_uar_path,  # 挂载全局 UAR
    )


    # 创建客户端和工作流
    client = GeminiClient()
    app = create_sota2_workflow(
        client=client,
        assets_input_dir=assets_input_dir,
        skip_vision=skip_vision,
        skip_asset_audit=skip_asset_audit,
    )

    # 运行工作流
    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}

    current_state = initial_state

    while True:
        try:
            # 运行直到完成或中断
            last_state = None
            async for event in app.astream(current_state, config=config, stream_mode="values"):
                last_state = event

            # 检查中断
            state_info = app.get_state(config)
            if not state_info.next:
                return last_state if isinstance(last_state, AgentState) else AgentState(**last_state)

            next_node = state_info.next[0]
            current_values = AgentState(**state_info.values) if isinstance(state_info.values, dict) else state_info.values

            print(f"\n{'='*60}")
            update_data = {}

            if next_node == "refiner":
                if not current_values.clarifier_answers:
                    print("💡 澄清问题:")
                    for i, q in enumerate(current_values.clarifier_questions, 1):
                        print(f"  {i}. [{q.get('category', '?')}] {q.get('question', q)}")

                    print("\n请回答以上问题 (每行一个答案，输入 DONE 结束):")
                    answers = []
                    while True:
                        line = input().strip()
                        if line.upper() == "DONE":
                            break
                        if line:
                            answers.append(line)

                    answer_dict = {}
                    for i, q in enumerate(current_values.clarifier_questions):
                        qid = q.get('id', f'q{i}')
                        answer_dict[qid] = answers[i] if i < len(answers) else "无回答"

                    update_data = {"clarifier_answers": answer_dict}

            elif next_node == "review_brief":
                print("📝 Project Brief:")
                print("-" * 40)
                print(current_values.project_brief[:2000])
                print("-" * 40)
                print("\n输入 'approve' 通过，或输入修改建议:")
                feedback = input().strip()

                if feedback.lower() in ["approve", "ok", "yes", "y", ""]:
                    update_data = {"brief_approved": True}
                else:
                    update_data = {"brief_approved": False, "user_brief_feedback": feedback}

            elif next_node == "review_outline":
                print("🏗️ Manifest (大纲):")
                print("-" * 40)
                if current_values.manifest:
                    print(f"标题: {current_values.manifest.project_title}")
                    print(f"章节数: {len(current_values.manifest.sections)}")
                    for s in current_values.manifest.sections:
                        print(f"  - {s.id}: {s.title} (~{s.estimated_words} 字)")
                print("-" * 40)
                print("\n输入 'approve' 通过，或输入修改建议:")
                feedback = input().strip()

                if feedback.lower() in ["approve", "ok", "yes", "y", ""]:
                    update_data = {"outline_approved": True}
                else:
                    update_data = {"outline_approved": False, "user_outline_feedback": feedback}

            elif next_node == "markdown_review":
                print("📋 Markdown 审核:")
                print(f"已完成章节: {len(current_values.completed_md_sections)}")
                for p in current_values.completed_md_sections:
                    print(f"  - {Path(p).name}")
                print("\n输入 'approve' 通过，或输入修改建议:")
                feedback = input().strip()

                if feedback.lower() in ["approve", "ok", "yes", "y", ""]:
                    update_data = {"markdown_approved": True}
                else:
                    update_data = {"markdown_approved": False, "user_markdown_feedback": feedback}

            # 更新状态
            if update_data:
                for k, v in update_data.items():
                    setattr(current_values, k, v)
                app.update_state(config, current_values.model_dump())

            current_state = None
            print(f"{'='*60}\n")

        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断")
            break
        except Exception as e:
            print(f"\n❌ 工作流错误: {e}")
            import traceback
            traceback.print_exc()
            raise

    return current_values