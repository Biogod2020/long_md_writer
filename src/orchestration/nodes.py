"""
Workflow Node Functions
定义所有 Agent 节点函数
"""

from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState

from ..agents.clarifier_agent import ClarifierAgent
from ..agents.refiner_agent import RefinerAgent
from ..agents.architect_agent import ArchitectAgent
from ..agents.techspec_agent import TechSpecAgent
from ..agents.writer_agent import WriterAgent
from ..agents.markdown_qa_agent import MarkdownQAAgent
from ..agents.design_tokens_agent import DesignTokensAgent
from ..agents.css_generator_agent import CSSGeneratorAgent
from ..agents.js_generator_agent import JSGeneratorAgent
from ..agents.transformer_agent import TransformerAgent
from ..agents.image_sourcing_agent import ImageSourcingAgent
from ..agents.assembler_agent import AssemblerAgent
from ..agents.visual_qa_agent import VisualQAAgent


class NodeFactory:
    """
    Node Function Factory
    创建所有节点函数，封装 Agent 实例
    """
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client
        
        # Initialize all agents
        self.clarifier = ClarifierAgent(client)
        self.refiner = RefinerAgent(client)
        self.architect = ArchitectAgent(client)
        self.techspec = TechSpecAgent(client)
        self.writer = WriterAgent(client)
        self.markdown_qa = MarkdownQAAgent(client)
        self.design_tokens = DesignTokensAgent(client)
        self.css_generator = CSSGeneratorAgent(client)
        self.js_generator = JSGeneratorAgent(client)
        self.transformer = TransformerAgent(client)
        self.image_sourcer = ImageSourcingAgent(client, debug=False, headless=True)
        self.assembler = AssemblerAgent(client)
        self.visual_qa = VisualQAAgent(client, debug=False, headless=True)
    
    # ================== Planning Nodes ==================
    
    def clarifier_node(self, state: AgentState) -> AgentState:
        """澄清节点 - 生成问题"""
        questions = self.clarifier.run(state)
        state.clarifier_questions = questions
        return state

    def refiner_node(self, state: AgentState) -> AgentState:
        """精炼节点 - 根据回答生成 Brief"""
        brief = self.refiner.run(
            state, 
            clarification_answers=state.clarifier_answers, 
            feedback=state.user_brief_feedback
        )
        state.project_brief = brief
        state.user_brief_feedback = None
        return state

    def review_brief_node(self, state: AgentState) -> AgentState:
        """Brief 审核节点 (interrupt point)"""
        return state

    def architect_node(self, state: AgentState) -> AgentState:
        """架构节点（生成 Manifest）"""
        feedback = getattr(state, 'user_outline_feedback', None)
        res = self.architect.run(state, feedback=feedback)
        if hasattr(res, 'user_outline_feedback'):
            res.user_outline_feedback = None
        return res
    
    def review_outline_node(self, state: AgentState) -> AgentState:
        """大纲审核节点 (interrupt point)"""
        return state

    def techspec_node(self, state: AgentState) -> AgentState:
        """技术规范节点 - 生成 SOTA Description"""
        return self.techspec.run(state)

    # ================== Writing Nodes ==================

    async def writer_node(self, state: AgentState) -> AgentState:
        """写手节点（写一个章节）"""
        return await self.writer.run(state)
    
    async def markdown_qa_node(self, state: AgentState) -> AgentState:
        """Markdown 质检节点"""
        return await self.markdown_qa.run(state)
    
    def markdown_review_node(self, state: AgentState) -> AgentState:
        """Markdown 人工审核节点 (interrupt point)"""
        return state

    # ================== Design Nodes ==================
    
    def design_tokens_node(self, state: AgentState) -> AgentState:
        """Design Tokens 节点"""
        return self.design_tokens.run(state)
    
    def css_generator_node(self, state: AgentState) -> AgentState:
        """CSS 生成器节点"""
        return self.css_generator.run(state)
    
    def js_generator_node(self, state: AgentState) -> AgentState:
        """JS 生成器节点"""
        return self.js_generator.run(state)

    # ================== Transformation Nodes ==================
    
    def transformer_node(self, state: AgentState) -> AgentState:
        """转换器节点（转换一个章节）"""
        return self.transformer.run(state)
    
    def image_sourcer_node(self, state: AgentState) -> AgentState:
        """图片采购节点"""
        return self.image_sourcer.run(state)

    # ================== Assembly Nodes ==================
    
    def assembler_node(self, state: AgentState) -> AgentState:
        """组装节点"""
        return self.assembler.run(state)
    
    def visual_qa_node(self, state: AgentState) -> AgentState:
        """视觉验收节点"""
        return self.visual_qa.run(state)
