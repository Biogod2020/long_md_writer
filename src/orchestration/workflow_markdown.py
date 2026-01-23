"""
SOTA 2.0 完整工作流 - Parallel Fulfillment & Section-Level QA
"""

import uuid
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState, AssetSource, AssetVQAStatus

# SOTA 2.0 Agents
from ..agents.asset_management import AssetIndexerAgent, AssetFulfillmentAgent, AssetCriticAgent
from ..agents.clarifier_agent import ClarifierAgent
from ..agents.refiner_agent import RefinerAgent
from ..agents.architect_agent import ArchitectAgent
from ..agents.techspec_agent import TechSpecAgent
from ..agents.writer_agent import WriterAgent
from ..agents.editorial_qa_agent import EditorialQAAgent
from ..agents.markdown_qa_agent import MarkdownQAAgent


from ..agents.visual_qa.renderer import PlaywrightRenderer


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
        self.renderer = None # 延迟初始化

        # Initialize agents
        self.asset_indexer = AssetIndexerAgent(client=self.client, input_dir=assets_input_dir, skip_vision=skip_vision)
        self.clarifier = ClarifierAgent(self.client)
        self.refiner = RefinerAgent(self.client)
        self.architect = ArchitectAgent(self.client)
        self.techspec = TechSpecAgent(self.client)
        self.writer = WriterAgent(self.client)
        self.fulfillment = AssetFulfillmentAgent(client=self.client, skip_generation=False, skip_search=True)
        self.markdown_qa = MarkdownQAAgent(self.client)

    async def asset_indexer_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 📦 Phase 0: Asset Indexing")
        return await self.asset_indexer.run_async(state)

    def clarifier_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 💡 Phase 1.1: Clarifier")
        state.clarifier_questions = self.clarifier.run(state)
        return state

    def refiner_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 📝 Phase 1.2: Refiner")
        state.project_brief = self.refiner.run(state, clarification_answers=state.clarifier_answers, feedback=state.user_brief_feedback)
        state.user_brief_feedback = None
        return state

    def review_brief_node(self, state: AgentState) -> AgentState: return state

    def architect_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 🏗️ Phase 1.3: Architect")
        feedback = getattr(state, 'user_outline_feedback', None)
        state = self.architect.run(state, feedback=feedback)
        state.user_outline_feedback = None
        return state

    def review_outline_node(self, state: AgentState) -> AgentState: return state

    def techspec_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 🔧 Phase 2: TechSpec")
        return self.techspec.run(state)

    async def writer_node(self, state: AgentState) -> AgentState:
        section_idx = state.current_section_index
        if state.manifest and section_idx < len(state.manifest.sections):
            section = state.manifest.sections[section_idx]
            print(f"\n[SOTA2] ✍️ Phase 3.1: Writer - {section.id}: {section.title}")
            
        # SOTA: 每次开始写新章节或重写时，重置 QA 迭代计数器
        state.md_qa_iterations = 0
        state.md_qa_needs_revision = False
        
        return await self.writer.run(state)

    async def markdown_qa_node(self, state: AgentState) -> AgentState:
        print(f"\n[SOTA2] 📋 Phase 3.2: Markdown QA (AI Internal Review)")
        # 只针对最新完成的章节
        return await self.markdown_qa.run(state)

    def markdown_review_node(self, state: AgentState) -> AgentState: return state

    async def batch_fulfillment_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 🎨 Phase 4.1: Parallel Asset Fulfillment")
        return await self.fulfillment.run_parallel_async(state)

    def batch_asset_review_node(self, state: AgentState) -> AgentState: return state


def create_sota2_workflow(
    client: Optional[GeminiClient] = None,
    assets_input_dir: str = "inputs",
    skip_vision: bool = False,
    skip_asset_audit: bool = False,
) -> StateGraph:
    nodes = SOTA2NodeFactory(client=client, assets_input_dir=assets_input_dir, skip_vision=skip_vision, skip_asset_audit=skip_asset_audit)
    workflow = StateGraph(AgentState)

    workflow.add_node("asset_indexer", nodes.asset_indexer_node)
    workflow.add_node("clarifier", nodes.clarifier_node)
    workflow.add_node("refiner", nodes.refiner_node)
    workflow.add_node("review_brief", nodes.review_brief_node)
    workflow.add_node("architect", nodes.architect_node)
    workflow.add_node("review_outline", nodes.review_outline_node)
    workflow.add_node("techspec", nodes.techspec_node)
    workflow.add_node("writer", nodes.writer_node)
    workflow.add_node("markdown_qa", nodes.markdown_qa_node)
    workflow.add_node("markdown_review", nodes.markdown_review_node)
    workflow.add_node("batch_fulfillment", nodes.batch_fulfillment_node)
    workflow.add_node("batch_asset_review", nodes.batch_asset_review_node)

    # --- Edges & Routing ---
    def should_review_brief(state: AgentState) -> Literal["architect", "refiner"]:
        return "architect" if getattr(state, "brief_approved", False) else "refiner"

    def should_review_outline(state: AgentState) -> Literal["techspec", "architect"]:
        return "techspec" if getattr(state, "outline_approved", False) else "architect"

    def should_continue_section_loop(state: AgentState) -> Literal["markdown_qa", "markdown_review", "writer"]:
        if getattr(state, "rewrite_needed", False): return "writer"
        
        # SOTA: 如果需要返工，强制回到 QA 节点进行 AI 再次审查
        if state.md_qa_needs_revision:
            # 只有在达到最大迭代次数且依然没通过时，才无奈交给人类
            if state.md_qa_iterations < 3:
                return "markdown_qa"
            else:
                print("  [Workflow] ⚠️ Reached max AI iterations, handing over to human...")
                return "markdown_review"
                
        # 如果通过了 AI 审查，进入人类审核环节
        return "markdown_review"

    def should_advance_to_fulfillment(state: AgentState) -> Literal["writer", "batch_fulfillment", "markdown_qa"]:
        # 如果人类没批准，或者 AI 认为还需要返工，必须回到 QA 节点
        if not state.markdown_approved or state.md_qa_needs_revision:
            return "markdown_qa"
            
        if state.all_sections_written():
            return "batch_fulfillment"
        return "writer"

    def should_finish_fulfillment(state: AgentState) -> Literal["batch_asset_review", "end"]:
        if state.asset_revision_needed: return "batch_asset_review"
        return "end"

    workflow.set_entry_point("asset_indexer")
    workflow.add_edge("asset_indexer", "clarifier")
    workflow.add_edge("clarifier", "refiner")
    workflow.add_edge("refiner", "review_brief")
    workflow.add_conditional_edges("review_brief", should_review_brief, {"architect": "architect", "refiner": "refiner"})
    workflow.add_edge("architect", "review_outline")
    workflow.add_conditional_edges("review_outline", should_review_outline, {"techspec": "techspec", "architect": "architect"})
    workflow.add_edge("techspec", "writer")
    workflow.add_edge("writer", "markdown_qa")
    workflow.add_conditional_edges("markdown_qa", should_continue_section_loop, {"markdown_qa": "markdown_qa", "markdown_review": "markdown_review", "writer": "writer"})
    workflow.add_conditional_edges("markdown_review", should_advance_to_fulfillment, {"writer": "writer", "batch_fulfillment": "batch_fulfillment", "markdown_qa": "markdown_qa"})
    workflow.add_conditional_edges("batch_fulfillment", should_finish_fulfillment, {"batch_asset_review": "batch_asset_review", "end": END})
    workflow.add_edge("batch_asset_review", "batch_fulfillment") # 重试机制

    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["refiner", "review_brief", "review_outline", "markdown_review", "batch_asset_review"]
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
    mounted_workspaces: Optional[dict[str, str]] = None,
) -> AgentState:
    if not job_id: job_id = f"sota2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workspace_path = Path(workspace_base) / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    for d in ["md", "agent_generated", "agent_sourced"]: (workspace_path / d).mkdir(exist_ok=True)

    initial_state = AgentState(job_id=job_id, workspace_path=str(workspace_path), user_intent=user_intent, reference_materials=reference_materials, debug_mode=debug_mode, uar_path=str(workspace_path / "assets.json"))
    uar = initial_state.get_uar()
    if mounted_workspaces:
        for name, path in mounted_workspaces.items(): uar.mount_workspace(name, path)

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
    debug_logs_path = workspace_path / "debug_logs"
    if debug_mode:
        debug_logs_path.mkdir(exist_ok=True)
    
    step_count = 0

    while True:
        try:
            # 运行直到完成或中断
            last_state = None
            async for event in app.astream(current_state, config=config, stream_mode="values"):
                last_state = event
                step_count += 1
                
                # 如果开启调试模式，保存每一状态的快照
                if debug_mode:
                    step_file = debug_logs_path / f"step_{step_count:03d}.json"
                    # 确保是 AgentState 对象
                    s_obj = last_state if isinstance(last_state, AgentState) else AgentState(**last_state)
                    step_file.write_text(s_obj.model_dump_json(indent=2), encoding="utf-8")

            # 检查中断

            state_info = app.get_state(config)
            if not state_info.next: return last_state if isinstance(last_state, AgentState) else AgentState(**last_state)
            
            next_node = state_info.next[0]
            current_values = AgentState(**state_info.values) if isinstance(state_info.values, dict) else state_info.values
            update_data = {}

            if next_node == "refiner":
                if not current_values.clarifier_answers:
                    print("💡 Clarifying Questions:")
                    for i, q in enumerate(current_values.clarifier_questions, 1): print(f"  {i}. {q.get('question')}")
                    print("\n(Type answers, 'DONE' to finish)")
                    ans = []
                    while True:
                        line = input().strip()
                        if line.upper() == "DONE": break
                        if line: ans.append(line)
                    update_data = {"clarifier_answers": {q['id']: ans[i] if i < len(ans) else "N/A" for i, q in enumerate(current_values.clarifier_questions)}}
            elif next_node == "review_brief":
                print("📝 Project Brief:")
                print("-" * 40)
                print(current_values.project_brief)
                print("-" * 40)
                print("\n输入 'approve' 通过，或输入修改建议:")
            elif next_node == "review_outline":
                print("🏗️ Manifest (大纲):")
                print("-" * 40)
                if current_values.manifest:
                    print(f"标题: {current_values.manifest.project_title}")
                    print(f"章节数: {len(current_values.manifest.sections)}")
                    for s in current_values.manifest.sections:
                        print(f"  - {s.id}: {s.title} (~{s.estimated_words} 字)")
                        print(f"    摘要: {s.summary}")
                print("-" * 40)
            elif next_node == "markdown_review":
                last_file = Path(current_values.completed_md_sections[-1]).name if current_values.completed_md_sections else "N/A"
                print(f"📋 Reviewing: {last_file}\nApprove? (y/feedback)")
                fb = input().strip()
                if fb.lower() in ['y', 'yes', '']:
                    update_data = {"markdown_approved": True}
                else:
                    update_data = {"markdown_approved": False, "user_markdown_feedback": fb}
            elif next_node == "batch_asset_review":
                print("\n" + "!"*20 + " BATCH ASSET FAILURE " + "!"*20)
                for fd in current_values.failed_directives:
                    print(f"- [{fd['id']}] in {fd['file']}: {fd['error']}")
                print("\nOptions: retry | skip | DONE")
                choice = input("> ").strip().lower()
                if choice == 'retry':
                    update_data = {"asset_revision_needed": False, "failed_directives": []}
                else:
                    update_data = {"asset_revision_needed": False}

            if update_data:
                for k, v in update_data.items(): setattr(current_values, k, v)
                app.update_state(config, current_values.model_dump())
            
            if next_node != "markdown_review" and current_values.markdown_approved:
                 app.update_state(config, {"markdown_approved": False})

            current_state = None
        except KeyboardInterrupt: break
        except Exception as e:
            import traceback; traceback.print_exc()
            raise e
    return current_values