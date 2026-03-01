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


from ..core.config import HEADLESS_MODE, NODE_PREF_HEAVY, NODE_PREF_LIGHT, NODE_PREF_PRO

class NodeFactory:
    """
    Node Function Factory
    创建所有节点函数，封装 Agent 实例
    """
    
    def __init__(self, client: Optional[GeminiClient] = None):
        # Base client used if nothing else specified
        self.client = client or GeminiClient()
        
        # SOTA 2.1: Specialized Clients for different workloads
        # Pro: Highest intelligence for Architecture (CLI First for large inputs)
        self.pro_client = GeminiClient(
            model=NODE_PREF_PRO["model"],
            model_provider=NODE_PREF_PRO["model_provider"],
            thinking_level=NODE_PREF_PRO["thinking_level"],
            prefer_first_provider=True
        )
        
        # SOTA 2.1: Pro client specialized for SVG creation (Polling enabled)
        self.svg_pro_client = GeminiClient(
            model=NODE_PREF_PRO["model"],
            model_provider=NODE_PREF_PRO["model_provider"],
            thinking_level=NODE_PREF_PRO["thinking_level"],
            prefer_first_provider=False
        )
        
        # Heavy: Dedicated to complex technical reasoning (Writer, editorial)
        self.heavy_client = GeminiClient(
            model_provider=NODE_PREF_HEAVY["model_provider"],
            thinking_level=NODE_PREF_HEAVY["thinking_level"],
            prefer_first_provider=True
        )
        
        # Light: Dedicated to structural tasks and SVG Fulfillment
        # prefer_first_provider=False allows natural load-balancing across accounts
        # to spread the 40s thinking cooldown for SVG creation/auditing.
        self.light_client = GeminiClient(
            model_provider=NODE_PREF_LIGHT["model_provider"],
            thinking_level=NODE_PREF_LIGHT["thinking_level"],
            prefer_first_provider=False
        )
        
        # Initialize all agents with appropriate client
        self.clarifier = ClarifierAgent(self.light_client)
        self.refiner = RefinerAgent(self.light_client)
        
        # Architect uses the Pro model for SOTA design
        self.architect = ArchitectAgent(self.pro_client)
        self.techspec = TechSpecAgent(self.light_client)
        
        # Writer and MarkdownQA require high intellectual depth
        self.writer = WriterAgent(self.heavy_client)
        self.markdown_qa = MarkdownQAAgent(self.heavy_client)
        
        self.design_tokens = DesignTokensAgent(self.light_client)
        self.css_generator = CSSGeneratorAgent(self.light_client)
        self.js_generator = JSGeneratorAgent(self.light_client)
        self.transformer = TransformerAgent(self.light_client)
        
        # SOTA 2.1: ImageSourcing uses tiered routing
        self.image_sourcer = ImageSourcingAgent(self.light_client, debug=False, headless=HEADLESS_MODE)
        
        from ..agents.asset_management.fulfillment import AssetFulfillmentAgent
        self.fulfillment_agent = AssetFulfillmentAgent(
            client=self.light_client, # Global ops use light
            debug=False,
            headless=HEADLESS_MODE,
            svg_pro_client=self.svg_pro_client, # SVG creation uses dedicated Polling client
            sourcing_client=self.light_client
        )
        
        self.assembler = AssemblerAgent(self.light_client)
        self.visual_qa = VisualQAAgent(self.client, debug=False, headless=True)
    
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
        """图片采购节点 (SOTA 2.1: Parallel Fulfillment)"""
        # SOTA: Return the result of the parallel async fulfillment run
        import asyncio
        return asyncio.run(self.fulfillment_agent.run_parallel_async(state))

    # ================== Assembly Nodes ==================
    
    def assembler_node(self, state: AgentState) -> AgentState:
        """组装节点"""
        return self.assembler.run(state)
    
    def visual_qa_node(self, state: AgentState) -> AgentState:
        """视觉验收节点"""
        return self.visual_qa.run(state)
