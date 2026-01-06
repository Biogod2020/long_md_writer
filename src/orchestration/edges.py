"""
Workflow Conditional Edge Functions
定义所有路由判断函数
"""

from typing import Literal
from ..core.types import AgentState


def should_review_brief(state: AgentState) -> Literal["architect", "refiner"]:
    """Brief 审核后路由"""
    if state.brief_approved:
        return "architect"
    return "refiner"


def should_review_outline(state: AgentState) -> Literal["techspec", "architect"]:
    """Outline 审核后路由"""
    if state.outline_approved:
        return "techspec"
    return "architect"


def should_continue_writing(state: AgentState) -> Literal["writer", "markdown_qa", "design_tokens"]:
    """判断是否继续写作"""
    if state.all_sections_written():
        if state.skip_markdown_qa:
            return "design_tokens"
        return "markdown_qa"
    
    if state.errors:
        # 即使报错，如果跳过 QA，也尝试继续后面流程或停下
        if state.skip_markdown_qa:
            return "design_tokens"
        return "markdown_qa"
        
    return "writer"


def should_run_md_qa_loop(state: AgentState) -> Literal["markdown_qa", "markdown_review", "writer"]:
    """判断 MD 自检循环"""
    if getattr(state, "rewrite_needed", False):
        return "writer"
    
    if state.md_qa_needs_revision and state.md_qa_iterations < 3:
        return "markdown_qa"
    return "markdown_review"


def should_review_markdown(state: AgentState) -> Literal["markdown_qa", "design_tokens"]:
    """判断人工审核结果"""
    if state.markdown_approved:
        return "design_tokens"
    return "markdown_qa"


def should_continue_transforming(state: AgentState) -> Literal["transformer", "image_sourcer"]:
    """判断是否继续转换"""
    if state.errors:
        return "image_sourcer"
    if state.all_sections_transformed():
        return "image_sourcer"
    return "transformer"


def should_reassemble(state: AgentState) -> Literal["assembler", "end"]:
    """视觉修复后是否重新拼装"""
    if state.vqa_needs_reassembly:
        return "assembler"
    return "end"
