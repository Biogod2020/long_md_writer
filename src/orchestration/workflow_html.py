"""
LangGraph Workflow Orchestration
串行执行 Agent 节点，管理状态流转

模块拆分:
- nodes.py: NodeFactory 类，封装所有 Agent 节点函数
- edges.py: 条件边路由函数
"""

import uuid
from pathlib import Path
from typing import Optional, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState

# 使用模块化的节点和边
from .nodes import NodeFactory
from .edges import (
    should_review_brief,
    should_review_outline,
    should_continue_writing,
    should_run_md_qa_loop,
    should_review_markdown,
    should_continue_transforming,
    should_reassemble,
)


def create_workflow(
    client: Optional[GeminiClient] = None,
    workspace_base: str = "./workspace"
) -> StateGraph:
    """
    创建 LangGraph 工作流
    
    节点执行顺序：
    1. Clarifier -> 生成澄清问题
    2. Refiner -> 生成 Project Brief
    3. Architect -> 生成 Manifest
    4. TechSpec -> 生成技术描述
    5. Writer (循环) -> 生成所有 Markdown
    6. Design -> 生成 CSS/JS/StyleMapping
    7. Transformer (循环) -> 转换所有 HTML
    8. Assembler -> 拼接最终 HTML
    """
    
    # 使用 NodeFactory 初始化所有节点
    nodes = NodeFactory(client)
    
    # 构建图
    workflow = StateGraph(AgentState)
    
    # 添加节点 (从 NodeFactory 获取)
    workflow.add_node("clarifier", nodes.clarifier_node)
    workflow.add_node("refiner", nodes.refiner_node)
    workflow.add_node("review_brief", nodes.review_brief_node)
    workflow.add_node("architect", nodes.architect_node)
    workflow.add_node("review_outline", nodes.review_outline_node)
    workflow.add_node("techspec", nodes.techspec_node)
    workflow.add_node("writer", nodes.writer_node)
    workflow.add_node("markdown_qa", nodes.markdown_qa_node)
    workflow.add_node("markdown_review", nodes.markdown_review_node)
    workflow.add_node("design_tokens", nodes.design_tokens_node)
    workflow.add_node("css_generator", nodes.css_generator_node)
    workflow.add_node("js_generator", nodes.js_generator_node)
    workflow.add_node("transformer", nodes.transformer_node)
    workflow.add_node("image_sourcer", nodes.image_sourcer_node)
    workflow.add_node("assembler", nodes.assembler_node)
    workflow.add_node("visual_qa", nodes.visual_qa_node)
    
    # 设置入口
    workflow.set_entry_point("clarifier")
    
    # 添加边
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
    workflow.add_edge("techspec", "writer")
    workflow.add_conditional_edges(
        "writer",
        should_continue_writing,
        {
            "writer": "writer",
            "markdown_qa": "markdown_qa",
            "design_tokens": "design_tokens",
        }
    )
    
    # Markdown QA 环路
    workflow.add_conditional_edges(
        "markdown_qa",
        should_run_md_qa_loop,
        {
            "markdown_qa": "markdown_qa",
            "markdown_review": "markdown_review",
            "writer": "writer",
        }
    )
    
    # Markdown 人工审核环路
    workflow.add_conditional_edges(
        "markdown_review",
        should_review_markdown,
        {
            "markdown_qa": "markdown_qa",     # 处理反馈
            "design_tokens": "design_tokens", # 审核通过
        }
    )
    # Design phase: Tokens -> CSS -> JS (sequential for now, could be parallel)
    workflow.add_edge("design_tokens", "css_generator")
    workflow.add_edge("css_generator", "js_generator")
    workflow.add_edge("js_generator", "transformer")
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
    
    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["refiner", "review_brief", "review_outline", "markdown_review"]
    )


def create_generation_workflow(
    client: Optional[GeminiClient] = None,
) -> StateGraph:
    """
    创建仅生成阶段的工作流 (Writer -> Assembler)
    假设 State 中已经有了 Manifest
    
    Enhanced with Design Tokens + CSS/JS Generator separation for SOTA design consistency.
    """
    # 初始化 Agent
    writer = WriterAgent(client)
    markdown_qa = MarkdownQAAgent(client)
    design_tokens_agent = DesignTokensAgent(client)
    css_generator = CSSGeneratorAgent(client)
    js_generator = JSGeneratorAgent(client)
    transformer = TransformerAgent(client)
    image_sourcer = ImageSourcingAgent(client, debug=False, headless=True)
    assembler = AssemblerAgent(client)
    visual_qa = VisualQAAgent(client, debug=False, headless=True)
    
    # Node functions
    def writer_node(state: AgentState) -> AgentState:
        res = writer.run(state)
        return res
    
    def markdown_qa_node(state: AgentState) -> AgentState:
        res = markdown_qa.run(state)
        return res
    
    def markdown_review_node(state: AgentState) -> AgentState:
        # The actual interrupt and state modification logic is handled in run_workflow
        # This node function just passes the state through, waiting for external update
        return state
    
    def design_tokens_node(state: AgentState) -> AgentState:
        """Design Tokens 节点"""
        res = design_tokens_agent.run(state)
        return res
    
    def css_generator_node(state: AgentState) -> AgentState:
        """CSS 生成器节点"""
        res = css_generator.run(state)
        return res
    
    def js_generator_node(state: AgentState) -> AgentState:
        """JS 生成器节点"""
        res = js_generator.run(state)
        return res
    
    def transformer_node(state: AgentState) -> AgentState:
        res = transformer.run(state)
        return res
    
    def image_sourcer_node(state: AgentState) -> AgentState:
        res = image_sourcer.run(state)
        return res
    
    def assembler_node(state: AgentState) -> AgentState:
        res = assembler.run(state)
        return res

    def visual_qa_node(state: AgentState) -> AgentState:
        res = visual_qa.run(state)
        return res
    
    # Conditional edges
    def should_continue_writing(state: AgentState) -> Literal["writer", "markdown_qa"]:
        if state.errors: return "markdown_qa"
        if state.all_sections_written(): return "markdown_qa"
        return "writer"

    def should_run_md_qa_loop(state: AgentState) -> Literal["markdown_qa", "markdown_review"]:
        if state.md_qa_needs_revision and state.md_qa_iterations < 3:
            return "markdown_qa"
        return "markdown_review"

    def should_review_markdown(state: AgentState) -> Literal["markdown_qa", "design_tokens"]:
        if state.markdown_approved: return "design_tokens"
        return "markdown_qa"
    
    def should_continue_transforming(state: AgentState) -> Literal["transformer", "image_sourcer"]:
        if state.errors: return "image_sourcer"
        if state.all_sections_transformed(): return "image_sourcer"
        return "transformer"

    def should_reassemble(state: AgentState) -> Literal["assembler", "end"]:
        if state.vqa_needs_reassembly:
            return "assembler"
        return "end"

    workflow = StateGraph(AgentState)
    
    workflow.add_node("writer", writer_node)
    workflow.add_node("markdown_qa", markdown_qa_node)
    workflow.add_node("markdown_review", markdown_review_node)
    workflow.add_node("design_tokens", design_tokens_node)
    workflow.add_node("css_generator", css_generator_node)
    workflow.add_node("js_generator", js_generator_node)
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
        {"writer": "writer", "markdown_qa": "markdown_qa"}
    )
    workflow.add_conditional_edges(
        "markdown_qa",
        should_run_md_qa_loop,
        {"markdown_qa": "markdown_qa", "markdown_review": "markdown_review"}
    )
    workflow.add_conditional_edges(
        "markdown_review",
        should_review_markdown,
        {"markdown_qa": "markdown_qa", "design_tokens": "design_tokens"}
    )
    # Design phase: Tokens -> CSS -> JS (sequential)
    workflow.add_edge("design_tokens", "css_generator")
    workflow.add_edge("css_generator", "js_generator")
    workflow.add_edge("js_generator", "transformer")
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

    
    return workflow.compile(checkpointer=MemorySaver())


from src.core.config import DEFAULT_BASE_URL, DEFAULT_AUTH_PASSWORD

async def run_workflow(
    raw_materials: str,
    reference_docs: Optional[list[str]] = None,
    workspace_base: str = "./workspace",
    job_id: Optional[str] = None,
    api_base_url: str = DEFAULT_BASE_URL,
    auth_token: str = DEFAULT_AUTH_PASSWORD,
    debug_mode: bool = False,
    skip_markdown_qa: bool = False,
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
        debug_mode: 是否开启调试模式
        skip_markdown_qa: 是否跳过文本质检
        
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
    
    debug_logs_path = workspace_path / "debug_logs"
    if debug_mode:
        debug_logs_path.mkdir(exist_ok=True)
    
    # 初始化状态
    initial_state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        raw_materials=raw_materials,
        reference_docs=reference_docs or [],
        debug_mode=debug_mode,
        skip_markdown_qa=skip_markdown_qa,
    )
    
    # 创建客户端
    client = GeminiClient(api_base_url=api_base_url, auth_token=auth_token)
    
    # 创建并编译工作流
    app = create_workflow(client=client)
    
    # 运行工作流 - 处理中断
    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}
    
    current_state = initial_state # 直接传递 AgentState 对象
    step_count = 0
    
    while True:
        try:
            # 运行直到完成或下一个中断
            last_state = None
            # 如果 current_state 为 None，表示是恢复运行；如果不为 None，表示是初次启动
            # 使用 astream 支持异步节点
            async for event in app.astream(current_state, config=config, stream_mode="values"):
                last_state = event
                step_count += 1
                
                # 如果开启调试模式，保存每一状态
                if debug_mode:
                    step_file = debug_logs_path / f"step_{step_count:03d}.json"
                    with open(step_file, "w", encoding="utf-8") as f:
                        # 使用 pydantic 的 model_dump_json 确保正确序列化
                        s_obj = AgentState(**last_state)
                        f.write(s_obj.model_dump_json(indent=2))
            
            # 检查中断状态
            state_info = app.get_state(config)
            if not state_info.next:
                # 确保返回 AgentState 而不是 dict
                return AgentState(**last_state) if isinstance(last_state, dict) else last_state
                
            next_node = state_info.next[0]
            current_values = AgentState(**state_info.values)
            
            print("\n" + "═"*60)
            
            # 准备要更新到 State 中的数据
            update_data = {}
            
            if next_node == "refiner":
                # 只有在没有回答时才提示问题
                if not current_values.clarifier_answers:
                    print("💡 STEP 1.1: CLARIFYING QUESTIONS")
                    print("The AI needs more information to create a precise brief. Please answer the following questions:\n")
                    for i, q in enumerate(current_values.clarifier_questions, 1):
                        print(f"{i}. [{q['category']}] {q['question']}")
                    
                    print("\n(Please provide your answers below. You can answer each by number or provide them all at once. Type 'DONE' on a new line to finish.)")
                    
                    all_answers = []
                    while True:
                        line = input().strip()
                        if line.upper() == "DONE":
                            break
                        if line:
                            all_answers.append(line)
                    
                    # 将所有输入合并并交给 Agent 自动匹配（或者通过简单规则拆分）
                    # 这里为了兼容旧格式，我们将汇总的回答存入一个特殊的 key，或者尝试分配给第一个问题
                    # 更稳妥的做法是更新 AgentState 以支持 block 形式的回答，但这里我们还是尝试按顺序分配
                    answers = {}
                    for i, q in enumerate(current_values.clarifier_questions):
                        if i < len(all_answers):
                            answers[q['id']] = all_answers[i]
                        else:
                            answers[q['id']] = "User provided general answer: " + "\n".join(all_answers)
                    
                    update_data = {"clarifier_answers": answers}
                else:
                    print("🔄 Refining project brief with your feedback...")
                    update_data = {} 
                
            elif next_node == "review_brief":
                print("📝 STEP 1.2: REVIEW PROJECT BRIEF")
                print("-" * 20)
                print(current_values.project_brief)
                print("-" * 20)
                print("\n[magenta]Options: type 'approve' to continue, or provide feedback to refine.[/magenta]")
                feedback = input("Your Feedback: ").strip()
                print(f"DEBUG: Received feedback input: '{feedback}'")
                
                if feedback.lower() in ["approve", "ok", "yes", "y", ""]:
                    update_data = {"brief_approved": True, "user_brief_feedback": None}
                else:
                    update_data = {"brief_approved": False, "user_brief_feedback": feedback}
            
            elif next_node == "review_outline":
                print("🧐 STEP 2.1: REVIEW OUTLINE (MANIFEST)")
                print("-" * 20)
                manifest = current_values.manifest
                if manifest:
                    print(f"[bold]Project Title:[/bold] {manifest.project_title}")
                    print(f"\n[bold]Project Vision & Philosophy:[/bold]\n{manifest.description[:1000]}...")
                    
                    print("\n" + "-"*10 + " [bold]Structural Breakdown[/bold] " + "-"*10)
                    for s in manifest.sections:
                        print(f"\n📍 [cyan]{s.id}[/cyan]: [bold]{s.title}[/bold] ({s.estimated_words} words)")
                        print(f"   [dim]{s.summary[:200]}...[/dim]")
                        
                        # Show key metadata
                        meta = s.metadata or {}
                        layout = meta.get("layout", "standard")
                        interactive = "✅ Interactive" if meta.get("has_interactive_element") else "❌ Static"
                        print(f"   [blue]Layout:[/blue] {layout} | [blue]Type:[/blue] {interactive}")
                        
                print("-" * 20)
                print("\n[magenta]Options: type 'approve' to continue, or provide feedback to refine.[/magenta]")
                feedback = input("Your Feedback: ").strip()
                
                if feedback.lower() in ["approve", "ok", "yes", "y", ""]:
                    update_data = {"outline_approved": True, "user_outline_feedback": None}
                else:
                    update_data = {"outline_approved": False, "user_outline_feedback": feedback}
                    
            elif next_node == "markdown_review":
                print("👤 STEP 3.1: HUMAN REVIEW - Markdown Content")
                print(f"Generated files: {[Path(p).name for p in current_values.completed_md_sections]}")
                print("\n[magenta]Options: type 'approve' to continue, or provide feedback to refine.[/magenta]")
                feedback = input("Your Feedback: ").strip()
                
                if feedback.lower() in ["approve", "ok", "yes", "y", ""]:
                    update_data = {"markdown_approved": True, "user_markdown_feedback": None}
                else:
                    update_data = {"markdown_approved": False, "user_markdown_feedback": feedback}
            
            else:
                print(f"Workflow paused at: {next_node}")
                input("Press Enter to continue...")
            
            # 核心：更新状态并一个设置 current_state 为 None 以便下次循环时 resume
            if update_data:
                # 获取最新的状态对象并合并我们的变更
                new_state = current_values
                for k, v in update_data.items():
                    setattr(new_state, k, v)
                
                # 更新到 Checkpointer
                app.update_state(config, new_state.model_dump())
            
            # 显示任何在节点中产生的错误
            if current_values.errors:
                print("\n❌ Errors captured during last step:")
                for err in current_values.errors:
                    print(f"  - {err}")
                current_values.errors = [] # 清理错误以便继续（如果可能）
                app.update_state(config, {"errors": []})

            current_state = None 
            print("═"*60 + "\n")
            continue
            
        except Exception as e:
            print(f"❌ Workflow Runtime Error: {e}")
            import traceback
            traceback.print_exc()
            raise e


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
