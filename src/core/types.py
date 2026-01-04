"""
Data types and models for the Magnum Opus HTML Agent system.
"""

from typing import Optional
from pydantic import BaseModel, Field


class SectionInfo(BaseModel):
    """章节信息"""
    id: str = Field(..., description="章节唯一标识符，例如 sec-1")
    title: str = Field(..., description="章节标题")
    summary: str = Field(..., description="章节摘要")
    estimated_words: int = Field(default=0, description="预估字数")
    file_path: Optional[str] = Field(default=None, description="Markdown 文件路径")


class Manifest(BaseModel):
    """项目清单 - 由架构师 Agent 生成"""
    project_title: str = Field(..., description="项目标题")
    author: Optional[str] = Field(default=None, description="作者")
    description: str = Field(..., description="项目描述")
    sections: list[SectionInfo] = Field(default_factory=list, description="章节列表")
    knowledge_map: dict[str, list[str]] = Field(
        default_factory=dict, 
        description="核心知识点映射，key 为章节 ID，value 为知识点列表"
    )
    
    def get_section_by_id(self, section_id: str) -> Optional[SectionInfo]:
        """根据 ID 获取章节"""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None


class StyleRule(BaseModel):
    """样式规则"""
    markdown_pattern: str = Field(..., description="Markdown 模式标识")
    css_selector: str = Field(..., description="对应的 CSS 选择器/类名")
    description: Optional[str] = Field(default=None, description="规则描述")


class StyleMapping(BaseModel):
    """样式契约 - 由设计师 Agent 生成"""
    rules: list[StyleRule] = Field(default_factory=list, description="样式规则列表")
    
    def get_css_for_pattern(self, pattern: str) -> Optional[str]:
        """根据 Markdown 模式获取 CSS 选择器"""
        for rule in self.rules:
            if rule.markdown_pattern == pattern:
                return rule.css_selector
        return None
    
    def to_dict(self) -> dict[str, str]:
        """转换为简单字典格式"""
        return {rule.markdown_pattern: rule.css_selector for rule in self.rules}


class AgentState(BaseModel):
    """LangGraph Agent 状态"""
    job_id: str = Field(..., description="任务 ID")
    workspace_path: str = Field(..., description="工作目录路径")
    
    # 输入
    raw_materials: str = Field(default="", description="原始素材/用户需求 (文本)")
    project_brief: str = Field(default="", description="经过 Refine 的项目需求书")
    images: list[dict] = Field(default_factory=list, description="图片素材 (base64 encoded inlineData)")
    reference_docs: list[str] = Field(default_factory=list, description="参考资料路径列表")
    
    # 数据契约
    manifest: Optional[Manifest] = Field(default=None, description="项目清单")
    style_mapping: Optional[StyleMapping] = Field(default=None, description="样式契约")
    
    # 进度跟踪
    current_section_index: int = Field(default=0, description="当前处理的章节索引")
    completed_md_sections: list[str] = Field(default_factory=list, description="已完成的 Markdown 章节路径")
    completed_html_sections: list[str] = Field(default_factory=list, description="已完成的 HTML 片段路径")
    
    # 设计资产
    css_path: Optional[str] = Field(default=None, description="CSS 文件路径")
    js_path: Optional[str] = Field(default=None, description="JS 文件路径")
    
    # 最终输出
    final_html_path: Optional[str] = Field(default=None, description="最终 HTML 文件路径")
    
    # 错误处理
    errors: list[str] = Field(default_factory=list, description="错误日志")
    
    # Human-in-the-Loop fields
    clarifier_questions: list[dict] = Field(default_factory=list, description="Clarifier 生成的问题列表")
    clarifier_answers: dict[str, str] = Field(default_factory=dict, description="用户对问题的回答")
    user_brief_feedback: Optional[str] = Field(default=None, description="用户对 Brief 的修改意见")
    user_outline_feedback: Optional[str] = Field(default=None, description="用户对大纲的修改意见")
    brief_approved: bool = Field(default=False, description="Brief 是否通过审核")
    outline_approved: bool = Field(default=False, description="大纲是否通过审核")
    vqa_iterations: int = Field(default=0, description="Visual QA 迭代次数")
    vqa_needs_reassembly: bool = Field(default=False, description="是否需要重新拼装")
    md_qa_iterations: int = Field(default=0, description="Markdown QA 迭代次数")
    md_qa_needs_revision: bool = Field(default=False, description="是否需要 MD 返工")
    
    def is_manifest_ready(self) -> bool:
        """检查清单是否就绪"""
        return self.manifest is not None
    
    def is_design_ready(self) -> bool:
        """检查设计资产是否就绪"""
        return (
            self.style_mapping is not None 
            and self.css_path is not None 
            and self.js_path is not None
        )
    
    def all_sections_written(self) -> bool:
        """检查所有章节是否已写完 Markdown"""
        if not self.manifest:
            return False
        return len(self.completed_md_sections) >= len(self.manifest.sections)
    
    def all_sections_transformed(self) -> bool:
        """检查所有章节是否已转换为 HTML"""
        if not self.manifest:
            return False
        return len(self.completed_html_sections) >= len(self.manifest.sections)
