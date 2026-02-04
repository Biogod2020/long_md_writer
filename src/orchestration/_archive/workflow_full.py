"""
Full Workflow with Human-in-the-Loop
Implements Clarifier -> Refiner -> Outline -> TechSpec -> Production pipeline
with interrupt points for user approval.
"""

from typing import Optional, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState
from ..agents.clarifier_agent import ClarifierAgent
from ..agents.refiner_agent import RefinerAgent
from ..agents.outline_agent import OutlineAgent
from ..agents.techspec_agent import TechSpecAgent
from ..agents.writer_agent import WriterAgent
from ..agents.design_agent import DesignAgent
from ..agents.transformer_agent import TransformerAgent
from ..agents.image_sourcing_agent import ImageSourcingAgent
from ..agents.assembler_agent import AssemblerAgent
from ..agents.visual_qa_agent import VisualQAAgent
from ..agents.markdown_qa_agent import MarkdownQAAgent


def create_full_workflow(
    client: Optional[GeminiClient] = None,
) -> tuple[StateGraph, MemorySaver]:
    """
    创建包含需求明确阶段的完整工作流
    
    Returns:
        (workflow, checkpointer) - 需要 checkpointer 来支持 interrupt/resume
    """
    
    # Initialize all agents
    clarifier = ClarifierAgent(client)
    refiner = RefinerAgent(client)
    outline_agent = OutlineAgent(client)
    techspec_agent = TechSpecAgent(client)
    writer = WriterAgent(client)
    designer = DesignAgent(client)
    transformer = TransformerAgent(client)
    image_sourcer = ImageSourcingAgent(client, debug=False, headless=True)
    assembler = AssemblerAgent(client)
    visual_qa = VisualQAAgent(client, debug=False, headless=True)
    markdown_qa = MarkdownQAAgent(client)
    
    # ============ Node Functions ============
    
    def clarifier_node(state: dict) -> dict:
        """生成澄清问题"""
        s = AgentState(**state)
        questions = clarifier.run(s)
        s.clarifier_questions = questions
        return s.model_dump()
    
    def refiner_node(state: dict) -> dict:
        """根据用户回答生成 Project Brief"""
        s = AgentState(**state)
        brief = refiner.run(s, clarification_answers=s.clarifier_answers, feedback=s.user_brief_feedback)
        s.project_brief = brief
        # Reset feedback after processing
        s.user_brief_feedback = None
        return s.model_dump()
    
    def review_brief_gate(state: dict) -> dict:
        """Brief 审核门 - 工作流会在此节点前中断"""
        # This is just a passthrough; interrupt happens before this node
        return state
    
    def outline_node(state: dict) -> dict:
        """生成文档大纲"""
        s = AgentState(**state)
        feedback = s.user_outline_feedback
        result = outline_agent.run(s, feedback=feedback)
        # Reset feedback after processing
        result.user_outline_feedback = None
        return result.model_dump()
    
    def review_outline_gate(state: dict) -> dict:
        """大纲审核门 - 工作流会在此节点前中断"""
        return state
    
    def techspec_node(state: dict) -> dict:
        """生成技术规格"""
        s = AgentState(**state)
        result = techspec_agent.run(s)
        return result.model_dump()
    
    def writer_node(state: dict) -> dict:
        """写一个章节"""
        s = AgentState(**state)
        res = writer.run(s)
        return res.model_dump()
    
    def design_node(state: dict) -> dict:
        """设计 CSS/JS"""
        s = AgentState(**state)
        res = designer.run(s)
        return res.model_dump()
    
    def markdown_qa_node(state: dict) -> dict:
        """Markdown 质检"""
        s = AgentState(**state)
        res = markdown_qa.run(s)
        return res.model_dump()
    
    def transformer_node(state: dict) -> dict:
        """转换一个章节"""
        s = AgentState(**state)
        res = transformer.run(s)
        return res.model_dump()
    
    def image_sourcer_node(state: dict) -> dict:
        """采购图片"""
        s = AgentState(**state)
        res = image_sourcer.run(s)
        return res.model_dump()
    
    def assembler_node(state: dict) -> dict:
        """拼装最终 HTML"""
        s = AgentState(**state)
        res = assembler.run(s)
        return res.model_dump()
    
    def visual_qa_node(state: dict) -> dict:
        """视觉验收"""
        s = AgentState(**state)
        res = visual_qa.run(s)
        return res.model_dump()
    
    # ============ Conditional Edge Functions ============
    
    def check_brief_approved(state: dict) -> Literal["outline", "refiner"]:
        """检查 Brief 是否通过审核"""
        if state.get("brief_approved", False):
            return "outline"
        return "refiner"
    
    def check_outline_approved(state: dict) -> Literal["techspec", "outline"]:
        """检查大纲是否通过审核"""
        if state.get("outline_approved", False):
            return "techspec"
        return "outline"
    
    def should_continue_writing(state: dict) -> Literal["writer", "markdown_qa"]:
        """判断是否继续写作"""
        s = AgentState(**state)
        if s.errors:
            return "markdown_qa"
        if s.all_sections_written():
            return "markdown_qa"
        return "writer"
    
    def after_markdown_qa(state: dict) -> Literal["markdown_qa", "design"]:
        """Markdown 质检后的路由"""
        if state.get("md_qa_needs_revision", False):
            return "markdown_qa"  # Re-check after fix
        return "design"
    
    def should_continue_transforming(state: dict) -> Literal["transformer", "image_sourcer"]:
        """判断是否继续转换"""
        s = AgentState(**state)
        if s.errors:
            return "image_sourcer"
        if s.all_sections_transformed():
            return "image_sourcer"
        return "transformer"
    
    def should_reassemble(state: dict) -> Literal["assembler", "end"]:
        """视觉修复后是否重新拼装"""
        if state.get("vqa_needs_reassembly", False):
            return "assembler"
        return "end"
    
    # ============ Build Graph ============
    
    workflow = StateGraph(dict)
    
    # Phase 0: Clarification
    workflow.add_node("clarifier", clarifier_node)
    
    # Phase 1: Refinement with approval loop
    workflow.add_node("refiner", refiner_node)
    workflow.add_node("review_brief", review_brief_gate)
    
    # Phase 2: Outline with approval loop
    workflow.add_node("outline", outline_node)
    workflow.add_node("review_outline", review_outline_gate)
    
    # Phase 3: TechSpec
    workflow.add_node("techspec", techspec_node)
    
    # Phase 4: Production pipeline
    workflow.add_node("writer", writer_node)
    workflow.add_node("markdown_qa", markdown_qa_node)
    workflow.add_node("design", design_node)
    workflow.add_node("transformer", transformer_node)
    workflow.add_node("image_sourcer", image_sourcer_node)
    workflow.add_node("assembler", assembler_node)
    workflow.add_node("visual_qa", visual_qa_node)
    
    # ============ Edges ============
    
    # Entry
    workflow.set_entry_point("clarifier")
    
    # Clarifier -> Refiner (assumes answers will be injected before resume)
    workflow.add_edge("clarifier", "refiner")
    
    # Refiner -> Review Brief
    workflow.add_edge("refiner", "review_brief")
    
    # Review Brief -> Outline (if approved) or back to Refiner (with feedback)
    workflow.add_conditional_edges(
        "review_brief",
        check_brief_approved,
        {"outline": "outline", "refiner": "refiner"}
    )
    
    # Outline -> Review Outline
    workflow.add_edge("outline", "review_outline")
    
    # Review Outline -> TechSpec (if approved) or back to Outline
    workflow.add_conditional_edges(
        "review_outline",
        check_outline_approved,
        {"techspec": "techspec", "outline": "outline"}
    )
    
    # TechSpec -> Writer
    workflow.add_edge("techspec", "writer")
    
    # Writer loop
    workflow.add_conditional_edges(
        "writer",
        should_continue_writing,
        {"writer": "writer", "markdown_qa": "markdown_qa"}
    )
    
    # Markdown QA loop
    workflow.add_conditional_edges(
        "markdown_qa",
        after_markdown_qa,
        {"markdown_qa": "markdown_qa", "design": "design"}
    )
    
    # Design -> Transformer
    workflow.add_edge("design", "transformer")
    
    # Transformer loop
    workflow.add_conditional_edges(
        "transformer",
        should_continue_transforming,
        {"transformer": "transformer", "image_sourcer": "image_sourcer"}
    )
    
    # Image sourcing -> Assembly
    workflow.add_edge("image_sourcer", "assembler")
    
    # Assembly -> Visual QA
    workflow.add_edge("assembler", "visual_qa")
    
    # Visual QA loop
    workflow.add_conditional_edges(
        "visual_qa",
        should_reassemble,
        {"assembler": "assembler", "end": END}
    )
    
    # Checkpointer for interrupt/resume
    checkpointer = MemorySaver()
    
    return workflow, checkpointer


def compile_full_workflow(client: Optional[GeminiClient] = None):
    """
    编译完整工作流，启用人机交互中断点
    
    中断点：
    - clarifier 之后（等待用户回答问题）
    - review_brief（等待用户审核 Brief）
    - review_outline（等待用户审核大纲）
    """
    workflow, checkpointer = create_full_workflow(client)
    
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["refiner", "review_brief", "review_outline"]
    )
