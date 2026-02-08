"""
SOTA 2.0 完整工作流 - Parallel Fulfillment & Section-Level QA
Integrated with LangGraph Native Persistence (AsyncSqliteSaver)
"""

import uuid
import os
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState

# SOTA 2.0 Agents
from ..agents.asset_management import AssetIndexerAgent, AssetFulfillmentAgent
from ..agents.clarifier_agent import ClarifierAgent
from ..agents.refiner_agent import RefinerAgent
from ..agents.architect_agent import ArchitectAgent
from ..agents.techspec_agent import TechSpecAgent
from ..agents.writer_agent import WriterAgent
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
        
        # SOTA 2.0: 物理注入命名空间前缀，确保全书 ID 隔离
        if state.manifest:
            from ..core.tools.namespace_manager import assign_namespaces_to_manifest
            state.manifest = assign_namespaces_to_manifest(state.manifest)
            print(f"  [Architect] Physical Namespace locked for {len(state.manifest.sections)} sections.")
            
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
            
        state.md_qa_iterations = 0
        state.md_qa_needs_revision = False
        return await self.writer.run(state)

    async def markdown_qa_node(self, state: AgentState) -> AgentState:
        print("\n[SOTA2] 📋 Phase 3.2: Markdown QA (AI Internal Review)")
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
    checkpointer: Optional[any] = None,
    interrupt_nodes: Optional[list[str]] = None
) -> any:
    """
    SOTA 2.0 Workflow Factory with native persistence support.
    """
    nodes = SOTA2NodeFactory(
        client=client, 
        assets_input_dir=assets_input_dir, 
        skip_vision=skip_vision, 
        skip_asset_audit=skip_asset_audit
    )
    workflow = StateGraph(AgentState)

    # Add Nodes
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

    # Routing Functions
    def should_review_brief(state: AgentState) -> Literal["architect", "refiner"]:
        return "architect" if getattr(state, "brief_approved", False) else "refiner"

    def should_review_outline(state: AgentState) -> Literal["techspec", "architect"]:
        return "techspec" if getattr(state, "outline_approved", False) else "architect"

    def should_continue_section_loop(state: AgentState) -> Literal["markdown_qa", "markdown_review", "writer"]:
        if getattr(state, "rewrite_needed", False): return "writer"
        if state.md_qa_needs_revision and state.md_qa_iterations < 3:
            return "markdown_qa"
        return "markdown_review"

    def should_advance_to_fulfillment(state: AgentState) -> Literal["writer", "batch_fulfillment", "markdown_qa"]:
        if not state.markdown_approved or state.md_qa_needs_revision:
            return "markdown_qa"
        if state.all_sections_written():
            return "batch_fulfillment"
        return "writer"

    def should_finish_fulfillment(state: AgentState) -> Literal["batch_asset_review", "end"]:
        if state.asset_revision_needed: return "batch_asset_review"
        return "end"

    # Define Edges
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
    workflow.add_edge("batch_asset_review", "batch_fulfillment")

    # Compile with persistence
    # Default interrupts for HITL if not provided
    default_interrupts = ["review_brief", "review_outline", "markdown_review", "batch_asset_review"]
    interrupts = interrupt_nodes if interrupt_nodes is not None else default_interrupts

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupts
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
    auto_mode: bool = False,
) -> AgentState:
    if not job_id: job_id = f"sota2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workspace_path = Path(workspace_base) / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    for d in ["md", "agent_generated", "agent_sourced"]: (workspace_path / d).mkdir(exist_ok=True)

    # Initialize checkpointer
    db_path = workspace_path / "checkpoints.db"
    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:

        initial_state = AgentState(
            job_id=job_id, 
            workspace_path=str(workspace_path), 
            user_intent=user_intent, 
            reference_materials=reference_materials, 
            debug_mode=debug_mode, 
            uar_path=str(workspace_path / "assets.json"),
            auto_mode=auto_mode
        )
        uar = initial_state.get_uar()
        if mounted_workspaces:
            for name, path in mounted_workspaces.items(): uar.mount_workspace(name, path)

        client = GeminiClient()
        app = create_sota2_workflow(
            client=client,
            assets_input_dir=assets_input_dir,
            skip_vision=skip_vision,
            skip_asset_audit=skip_asset_audit,
            checkpointer=checkpointer
        )

        config = {"configurable": {"thread_id": job_id}}
        current_state = initial_state
        
        while True:
            try:
                # Native LangGraph execution with checkpoints
                async for event in app.astream(current_state, config=config, stream_mode="values"):
                    last_state = event

                # Check if workflow is finished or interrupted
                state_info = await app.aget_state(config)
                if not state_info.next:
                    return last_state if isinstance(last_state, AgentState) else AgentState(**last_state)
                
                # Handle Interrupts (Simplified for run_sota2_workflow utility)
                next_node = state_info.next[0]
                print(f"\n[Workflow] ⏸️ Interrupted at node: {next_node}")
                
                # For this utility, we just auto-approve if auto_mode, else error out or wait
                if auto_mode:
                    update = {}
                    if next_node == "review_brief": update = {"brief_approved": True}
                    elif next_node == "review_outline": update = {"outline_approved": True}
                    elif next_node == "markdown_review": update = {"markdown_approved": True}
                    
                    if update:
                        await app.aupdate_state(config, update)
                        current_state = None # Resume
                        continue
                
                print("Manual intervention required. Please use the Breakpoint Harness for interactive debugging.")
                return AgentState(**state_info.values)

            except Exception as e:
                import traceback; traceback.print_exc()
                raise e