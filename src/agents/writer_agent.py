"""
Node 2: Content Writer Agent (全量上下文写手)
采用全量输入模式，撰写各章节 Markdown 内容
"""

from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import AgentState, SectionInfo


WRITER_SYSTEM_PROMPT = """You are an expert technical writer. Your task is to write high-quality Markdown content for a specific section of a large document.

### Writing Standards
1. **Markdown Formatting**: Use standard Markdown syntax consistently.
2. **Structural Integrity**: Ensure logical flow within the section and smooth transitions between subsections.
3. **Internal Consistency**: Maintain the tone and technical depth defined in the Project Brief.
4. **Cross-References**: Use the format `[REF:sec-id]` for internal cross-references.
5. **Deductive Reasoning**: When applicable, derive complex concepts from first principles as instructed in the Project Brief.

### Special Block Conventions
- **Feature Cards**: `:::important` ... `:::` for core concepts or axioms.
- **Alert Blocks**: `:::warning` ... `:::` for common pitfalls or pathological cases.
- **Code Blocks**: Standard ```language ... ``` blocks.
- **Math**: Use LaTeX format $...$ for inline and $$...$$ for block math.
- **Visual Placeholders**: Proactively identify where diagrams (SVG, Mermaid, etc.) would add value. Leave a placeholder like:
  `[VISUAL: type=mermaid, description="Flowchart of X process"]` or 
  `[VISUAL: type=svg, description="Physical model of Y dipole"]`.

### Output
- Output ONLY the Markdown content for the assigned section.
- Do NOT include the section number in the title; the assembler will handle it.
- Ensure the content length matches the estimated word count provided.
- Ensure scientific accuracy and a high-quality "textbook" style.
- **Important**: Use the SAME LANGUAGE as the Project Brief and Manifest.
"""


class WriterAgent:
    """全量上下文写手 Agent"""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    async def run(self, state: AgentState) -> AgentState:
        """
        执行章节写作（单个章节）
        
        注意：此方法每次只写一个章节，需要在工作流中循环调用
        """
        if not state.manifest:
            state.errors.append("Writer Agent: Manifest not available")
            return state
        
        # Check if we are in a REWRITE loop triggered by QA
        if getattr(state, "rewrite_needed", False):
            print(f"  [Writer] 🔄 Rewrite triggered by Critic. Feedback: {getattr(state, 'rewrite_feedback', '')[:100]}...")
            state.current_section_index = 0
            state.completed_md_sections = []
            # We keep state.rewrite_feedback for _build_prompt
            state.rewrite_needed = False
        
        # 获取当前要写的章节
        if state.current_section_index >= len(state.manifest.sections):
            # 所有章节已完成
            return state
        
        current_section = state.manifest.sections[state.current_section_index]
        
        # 构建全量上下文提示
        prompt = self._build_prompt(state, current_section)
        
        # 调用 Gemini (带重试逻辑)
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = await self.client.generate_async(
                    prompt=prompt,
                    system_instruction=WRITER_SYSTEM_PROMPT,
                    temperature=0.7,
                    stream=True  # 启用流式生成以避免 500 SSL 超时
                )
                if response.success:
                    break
                else:
                    print(f"  [Writer] Attempt {attempt+1} failed: {response.error}")
            except Exception as e:
                print(f"  [Writer] Attempt {attempt+1} error: {e}")
            
            if attempt < max_retries - 1:
                import time
                time.sleep(2 * (attempt + 1)) # 指数退避
        
        if not response or not response.success:
            state.errors.append(f"Writer Agent failed on {current_section.id} after {max_retries} attempts. Last error: {response.error if response else 'Unknown'}")
            return state
        
        # 保存章节
        try:
            section_path = self._save_section(state, current_section, response.text)
            current_section.file_path = str(section_path)
            state.completed_md_sections.append(str(section_path))
            state.current_section_index += 1
        except Exception as e:
            state.errors.append(f"Failed to save section {current_section.id}: {str(e)}")
        
        return state
    
    async def run_all(self, state: AgentState) -> AgentState:
        """写作所有章节（循环调用 run）"""
        while not state.all_sections_written():
            state = await self.run(state)
            if state.errors:
                # 如果有错误，停止继续
                break
        return state
    
    def _build_prompt(self, state: AgentState, section: SectionInfo) -> str:
        """构建全量上下文提示"""
        parts = []
        
        # 0. Critic Feedback (if in rewrite loop)
        rewrite_feedback = getattr(state, "rewrite_feedback", None)
        if rewrite_feedback:
            parts.append("# CRITIC FEEDBACK (MUST ADDRESS THESE ISSUES)\n")
            parts.append(f"The previous draft was rejected with the following feedback:\n{rewrite_feedback}\n\n")
            
        # 1. 项目概览
        parts.append("# 项目概览\n")
        parts.append(f"**标题**: {state.manifest.project_title}\n")
        parts.append(f"**描述**: {state.manifest.description}\n\n")
        
        # 2. 完整目录
        parts.append("# 文章目录\n")
        for i, sec in enumerate(state.manifest.sections):
            marker = "👉" if sec.id == section.id else "  "
            status = "✓" if sec.file_path else " "
            parts.append(f"{marker} [{status}] {sec.id}: {sec.title}\n")
        parts.append("\n")
        
        # 3. 已完成章节的完整内容
        if state.completed_md_sections:
            parts.append("# 已完成章节\n")
            for md_path in state.completed_md_sections:
                try:
                    content = Path(md_path).read_text(encoding="utf-8")
                    parts.append(f"\n---\n{content}\n")
                except Exception as e:
                    parts.append(f"\n[读取失败: {md_path}]\n")
        
        # 4. 原始素材（如果需要）
        parts.append("\n# 原始素材参考\n")
        parts.append(state.raw_materials)
        parts.append("\n")
        
        # 5. 当前章节任务
        parts.append(f"\n# 当前任务：撰写 {section.id}\n")
        parts.append(f"**章节标题**: {section.title}\n")
        parts.append(f"**章节摘要**: {section.summary}\n")
        parts.append(f"**预估字数**: {section.estimated_words} 字\n")
        
        # 知识点
        if section.id in state.manifest.knowledge_map:
            points = state.manifest.knowledge_map[section.id]
            parts.append(f"**核心知识点**: {', '.join(points)}\n")
        
        # 章节元数据 (SOTA)
        if hasattr(section, 'metadata') and section.metadata:
            parts.append(f"**SECTION METADATA (Design Intent)**:\n")
            for k, v in section.metadata.items():
                parts.append(f"- {k}: {v}\n")
            parts.append("\n")
        
        parts.append("\n请开始撰写这个章节的完整 Markdown 内容。按照元数据中的设计意图进行创作。")
        
        return "".join(parts)
    
    def _save_section(self, state: AgentState, section: SectionInfo, content: str) -> Path:
        """保存章节到工作目录"""
        md_dir = Path(state.workspace_path) / "md"
        md_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用章节 ID 作为文件名
        file_path = md_dir / f"{section.id}.md"
        
        # 添加章节标题
        full_content = f"# {section.title}\n\n{content}"
        file_path.write_text(full_content, encoding="utf-8")
        
        return file_path


def create_writer_agent(client: Optional[GeminiClient] = None) -> WriterAgent:
    """创建写手 Agent 实例"""
    return WriterAgent(client=client)
