"""
LangGraph Workflow Orchestration
串行执行 Agent 节点，管理状态流转
"""

import uuid
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass

from langgraph.graph import StateGraph, END

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState
from ..agents.architect_agent import ArchitectAgent
from ..agents.writer_agent import WriterAgent
from ..agents.design_agent import DesignAgent
from ..agents.transformer_agent import TransformerAgent
from ..agents.image_sourcing_agent import ImageSourcingAgent
from ..agents.assembler_agent import AssemblerAgent
from ..agents.visual_qa_agent import VisualQAAgent


def create_workflow(
    client: Optional[GeminiClient] = None,
    workspace_base: str = "./workspace"
) -> StateGraph:
    """
    创建 LangGraph 工作流
    
    节点执行顺序：
    1. Architect -> 生成 Manifest
    2. Writer (循环) -> 生成所有 Markdown
    3. Design -> 生成 CSS/JS/StyleMapping
    4. Transformer (循环) -> 转换所有 HTML
    5. Assembler -> 拼接最终 HTML
    """
    
    # 初始化 Agent
    architect = ArchitectAgent(client)
    writer = WriterAgent(client)
    designer = DesignAgent(client)
    transformer = TransformerAgent(client)
    image_sourcer = ImageSourcingAgent(client, debug=False, headless=True)
    assembler = AssemblerAgent(client)
    visual_qa = VisualQAAgent(client, debug=False, headless=True)
    
    # 定义节点函数
    def architect_node(state: dict) -> dict:
        """架构师节点"""
        s = AgentState(**state)
        res = architect.run(s)
        return res.model_dump()
    
    def writer_node(state: dict) -> dict:
        """写手节点（写一个章节）"""
        s = AgentState(**state)
        res = writer.run(s)
        return res.model_dump()
    
    def design_node(state: dict) -> dict:
        """设计组节点"""
        s = AgentState(**state)
        res = designer.run(s)
        return res.model_dump()
    
    def transformer_node(state: dict) -> dict:
        """转换器节点（转换一个章节）"""
        s = AgentState(**state)
        res = transformer.run(s)
        return res.model_dump()
    
    def image_sourcer_node(state: dict) -> dict:
        """图片采购节点"""
        s = AgentState(**state)
        res = image_sourcer.run(s)
        return res.model_dump()
    
    def assembler_node(state: dict) -> dict:
        """质检员节点"""
        s = AgentState(**state)
        res = assembler.run(s)
        return res.model_dump()
    
    def visual_qa_node(state: dict) -> dict:
        """视觉验收节点"""
        s = AgentState(**state)
        res = visual_qa.run(s)
        return res.model_dump()
    
    # 定义条件边
    def should_continue_writing(state: dict) -> Literal["writer", "design"]:
        """判断是否继续写作"""
        s = AgentState(**state)
        if s.errors:
            return "design"  # 有错误，跳过继续写作
        if s.all_sections_written():
            return "design"
        return "writer"
    
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
    
    # 构建图
    workflow = StateGraph(dict) # 使用 dict 作为基础状态类型
    
    # 添加节点
    workflow.add_node("architect", architect_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("design", design_node)
    workflow.add_node("transformer", transformer_node)
    workflow.add_node("image_sourcer", image_sourcer_node)
    workflow.add_node("assembler", assembler_node)
    workflow.add_node("visual_qa", visual_qa_node)
    
    # 设置入口
    workflow.set_entry_point("architect")
    
    # 添加边
    workflow.add_edge("architect", "writer")
    workflow.add_conditional_edges(
        "writer",
        should_continue_writing,
        {
            "writer": "writer",
            "design": "design",
        }
    )
    workflow.add_edge("design", "transformer")
    workflow.add_conditional_edges(
        "transformer",
        should_continue_transforming,
        {
            "transformer": "transformer",
            "image_sourcer": "image_sourcer",
        }
    )
    workflow.add_edge("image_sourcer", "assembler")
    workflow.add_edge("assembler", "visual_qa")
    workflow.add_conditional_edges(
        "visual_qa",
        should_reassemble,
        {
            "assembler": "assembler",
            "end": END
        }
    )
    
    return workflow


def create_generation_workflow(
    client: Optional[GeminiClient] = None,
) -> StateGraph:
    """
    创建仅生成阶段的工作流 (Writer -> Assembler)
    假设 State 中已经有了 Manifest
    """
    # 初始化 Agent
    writer = WriterAgent(client)
    designer = DesignAgent(client)
    transformer = TransformerAgent(client)
    image_sourcer = ImageSourcingAgent(client, debug=False, headless=True)
    assembler = AssemblerAgent(client)
    visual_qa = VisualQAAgent(client, debug=False, headless=True)
    
    # Node functions
    def writer_node(state: dict) -> dict:
        s = AgentState(**state)
        res = writer.run(s)
        return res.model_dump()
    
    def design_node(state: dict) -> dict:
        s = AgentState(**state)
        res = designer.run(s)
        return res.model_dump()
    
    def transformer_node(state: dict) -> dict:
        s = AgentState(**state)
        res = transformer.run(s)
        return res.model_dump()
    
    def image_sourcer_node(state: dict) -> dict:
        s = AgentState(**state)
        res = image_sourcer.run(s)
        return res.model_dump()
    
    def assembler_node(state: dict) -> dict:
        s = AgentState(**state)
        res = assembler.run(s)
        return res.model_dump()

    def visual_qa_node(state: dict) -> dict:
        s = AgentState(**state)
        res = visual_qa.run(s)
        return res.model_dump()
    
    # Conditional edges
    def should_continue_writing(state: dict) -> Literal["writer", "design"]:
        s = AgentState(**state)
        if s.errors: return "design"
        if s.all_sections_written(): return "design"
        return "writer"
    
    def should_continue_transforming(state: dict) -> Literal["transformer", "image_sourcer"]:
        s = AgentState(**state)
        if s.errors: return "image_sourcer"
        if s.all_sections_transformed(): return "image_sourcer"
        return "transformer"

    def should_reassemble(state: dict) -> Literal["assembler", "end"]:
        if state.get("vqa_needs_reassembly", False):
            return "assembler"
        return "end"

    workflow = StateGraph(dict)
    
    workflow.add_node("writer", writer_node)
    workflow.add_node("design", design_node)
    workflow.add_node("transformer", transformer_node)
    workflow.add_node("image_sourcer", image_sourcer_node)
    workflow.add_node("assembler", assembler_node)
    workflow.add_node("visual_qa", visual_qa_node)
    
    # Entry point: Writer
    workflow.set_entry_point("writer")
    
    # Edges
    workflow.add_conditional_edges(
        "writer",
        should_continue_writing,
        {"writer": "writer", "design": "design"}
    )
    workflow.add_edge("design", "transformer")
    workflow.add_conditional_edges(
        "transformer",
        should_continue_transforming,
        {"transformer": "transformer", "image_sourcer": "image_sourcer"}
    )
    workflow.add_edge("image_sourcer", "assembler")
    workflow.add_edge("assembler", "visual_qa")
    workflow.add_conditional_edges(
        "visual_qa",
        should_reassemble,
        {"assembler": "assembler", "end": END}
    )

    
    return workflow


def run_workflow(
    raw_materials: str,
    reference_docs: Optional[list[str]] = None,
    workspace_base: str = "./workspace",
    job_id: Optional[str] = None,
    api_base_url: str = "http://localhost:7860",
    auth_token: Optional[str] = None,
) -> AgentState:
    """
    运行完整工作流
    
    Args:
        raw_materials: 原始素材/用户需求
        reference_docs: 参考文档路径列表
        workspace_base: 工作目录基础路径
        job_id: 任务 ID（可选，默认自动生成）
        api_base_url: Gemini API 代理地址
        auth_token: 认证 token
        
    Returns:
        最终的 AgentState
    """
    # 生成 job_id
    if not job_id:
        job_id = str(uuid.uuid4())[:8]
    
    # 创建工作目录
    workspace_path = Path(workspace_base) / job_id
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "md").mkdir(exist_ok=True)
    (workspace_path / "html").mkdir(exist_ok=True)
    (workspace_path / "assets").mkdir(exist_ok=True)
    
    # 初始化状态
    initial_state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        raw_materials=raw_materials,
        reference_docs=reference_docs or [],
    )
    
    # 创建客户端
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    # 创建并编译工作流
    workflow = create_workflow(client=client)
    app = workflow.compile()
    
    # 运行工作流
    result = app.invoke(initial_state.model_dump())
    return AgentState(**result)


class WorkflowRunner:
    """工作流运行器，提供更灵活的控制"""
    
    def __init__(
        self,
        api_base_url: str = "http://localhost:7860",
        auth_token: Optional[str] = None,
        workspace_base: str = "./workspace",
    ):
        self.client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
        self.workspace_base = workspace_base
        self.workflow = create_workflow(client=self.client)
        self.app = self.workflow.compile()
    
    def run(
        self,
        raw_materials: str,
        reference_docs: Optional[list[str]] = None,
        job_id: Optional[str] = None,
    ) -> AgentState:
        """运行工作流"""
        if not job_id:
            job_id = str(uuid.uuid4())[:8]
        
        workspace_path = Path(self.workspace_base) / job_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        (workspace_path / "md").mkdir(exist_ok=True)
        (workspace_path / "html").mkdir(exist_ok=True)
        (workspace_path / "assets").mkdir(exist_ok=True)
        
        initial_state = AgentState(
            job_id=job_id,
            workspace_path=str(workspace_path),
            raw_materials=raw_materials,
            reference_docs=reference_docs or [],
        )
        
        result = self.app.invoke(initial_state.model_dump())
        return AgentState(**result)
    
    def run_from_file(self, input_file: str, job_id: Optional[str] = None) -> AgentState:
        """从文件读取素材并运行"""
        raw_materials = Path(input_file).read_text(encoding="utf-8")
        return self.run(raw_materials=raw_materials, job_id=job_id)
