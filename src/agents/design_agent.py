"""
Node 3-5: Design Team (视觉与交互设计组)
包含 Designer, CSS Coder, JS Scripter 三个角色
"""

from pathlib import Path
from typing import Optional
import json

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import AgentState, StyleMapping, StyleRule


DESIGNER_SYSTEM_PROMPT = """You are a senior UI/UX designer. Your task is to design a visual design system for a technical document based on its content and objectives.

Your output should be a JSON style guide including:
1. Color Palette (Primary, Accent, Background, Text)
2. Typography (Headings, Body, Code)
3. Spacing System
4. Component Styles (Cards, Callouts, Code Blocks, Quotes)

Ensure the design reflects the tone and complexity described in the Project Brief.
"""

CSS_CODER_SYSTEM_PROMPT = """You are a CSS expert. Convert a visual design guide into production-ready CSS.

Requirements:
1. Use CSS variables for design tokens.
2. Follow BEM naming conventions.
3. Responsive design support.
4. Include print styles.
5. High accessibility standards.

Also output a Style Mapping JSON that maps Markdown elements/patterns to CSS classes.
Example Mapping:
- "important_card" -> "section.card.card--important"
- "formula_block" -> "div.math-block"

Output Format:
1. CSS code in ```css block.
2. Style Mapping JSON in ```json block.
"""

JS_SCRIPTER_SYSTEM_PROMPT = """You are a JavaScript expert. Implement interactive features for a technical document.

Features to implement:
1. Table of Contents (TOC) with scroll spy.
2. Code block utilities (copy button).
3. Math rendering support (MathJax/KaTeX).
4. Reading progress bar.
5. Dark mode toggle.
6. Core logic for any custom interactive elements mentioned in the Project Description.

Requirements:
1. Vanilla JavaScript, no frameworks.
2. ES6+ syntax.
3. Clean, modular code.

Output the complete JavaScript code in a ```javascript block.
"""


class DesignAgent:
    """视觉与交互设计组 Agent"""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """执行设计流程：Designer -> CSS Coder -> JS Scripter"""
        
        # 读取所有 Markdown 内容
        full_content = self._get_full_markdown(state)
        
        if not full_content:
            state.errors.append("Design Agent: No Markdown content available")
            return state
        
        # Step 1: 视觉设计
        design_guide = self._run_designer(state, full_content)
        if not design_guide:
            state.errors.append("Design Agent: Designer failed")
            return state
        
        # Step 2: CSS 编码
        css_result = self._run_css_coder(state, full_content, design_guide)
        if not css_result:
            state.errors.append("Design Agent: CSS Coder failed")
            return state
        
        css_code, style_mapping = css_result
        
        # Step 3: JS 脚本
        js_code = self._run_js_scripter(state, full_content)
        if not js_code:
            state.errors.append("Design Agent: JS Scripter failed")
            return state
        
        # 保存设计资产
        try:
            state = self._save_assets(state, css_code, js_code, style_mapping)
        except Exception as e:
            state.errors.append(f"Design Agent: Failed to save assets: {e}")
        
        return state
    
    def _get_full_markdown(self, state: AgentState) -> str:
        """读取所有已完成的 Markdown 内容"""
        parts = []
        for md_path in state.completed_md_sections:
            try:
                content = Path(md_path).read_text(encoding="utf-8")
                parts.append(content)
            except Exception:
                pass
        return "\n\n---\n\n".join(parts)
    
    def _run_designer(self, state: AgentState, full_content: str) -> Optional[str]:
        """运行视觉设计师"""
        prompt = f"""# Project Brief (User Goals & Audience)
{state.project_brief if state.project_brief else "N/A"}

# Technical Specification (Global Context)
{state.manifest.description}

# Document Content Preview
{full_content[:8000]}

---

Based on the above context, design a visual style guide. Consider the content type, target audience, and technical requirements.
If you see suggestions for SVG animations, CSS effects, or interactive slides in the Technical Specification, include them in your design guide.
Output a JSON style guide."""
        
        response = self.client.generate(
            prompt=prompt,
            system_instruction=DESIGNER_SYSTEM_PROMPT,
            temperature=0.7,
        )
        
        if not response.success:
            state.errors.append(f"Designer API Error: {response.error}")
            return None
            
        return response.text
    
    def _run_css_coder(self, state: AgentState, full_content: str, design_guide: str) -> Optional[tuple[str, StyleMapping]]:
        """运行 CSS 编码器"""
        prompt = f"""# 项目全景描述 (Global Context)
{state.manifest.description}

# 视觉设计指南
{design_guide}

# 文档内容预览
{full_content[:5000]}...

---

请基于设计指南，生成：
1. 完整的 CSS 代码 (如果是 SOTA 讲义，请包含必要的动画关键帧、玻璃拟态样式等)
2. Style Mapping JSON（Markdown 元素 -> CSS 类名映射）
"""
        
        response = self.client.generate(
            prompt=prompt,
            system_instruction=CSS_CODER_SYSTEM_PROMPT,
            temperature=0.4,
        )
        
        if not response.success:
            state.errors.append(f"CSS Coder API Error: {response.error}")
            return None
        
        # 解析 CSS 和 Style Mapping
        return self._parse_css_response(response.text)
    
    def _run_js_scripter(self, state: AgentState, full_content: str) -> Optional[str]:
        """运行 JS 脚本编写器"""
        prompt = f"""# 项目全景描述 (Global Context)
{state.manifest.description}

# 文档结构预览
{full_content[:3000]}...

---

请生成实现交互功能的 JavaScript 代码。
除了基础功能（TOC, 代码高亮等），如果 Description 中提到了 SVG 动画、交互 Slide 或向量投影模型，请在这里尝试实现其核心逻辑或预留接口。
"""
        
        response = self.client.generate(
            prompt=prompt,
            system_instruction=JS_SCRIPTER_SYSTEM_PROMPT,
            temperature=0.4,
        )
        
        if not response.success:
            state.errors.append(f"JS Scripter API Error: {response.error}")
            return None
        
        # 提取 JavaScript 代码
        return self._extract_code_block(response.text, "javascript")
    
    def _parse_css_response(self, text: str) -> Optional[tuple[str, StyleMapping]]:
        """解析 CSS Coder 的响应"""
        css_code = self._extract_code_block(text, "css")
        json_text = self._extract_code_block(text, "json")
        
        if not css_code:
            return None
        
        # 解析 Style Mapping
        style_mapping = StyleMapping(rules=[])
        if json_text:
            try:
                data = json.loads(json_text)
                for key, value in data.items():
                    # 增强鲁棒性：如果 LLM 返回了嵌套字典而不是字符串选择器
                    if isinstance(value, dict):
                        # 如果是字典，可能包含了 tag, class 等，尝试合并或转为字符串
                        # 兼容处理：转换为 key:val; 格式或者只取 class
                        if "class" in value:
                            value_str = value["class"]
                        else:
                            value_str = " ".join([f"{v}" for v in value.values() if isinstance(v, str)])
                    else:
                        value_str = str(value)
                        
                    style_mapping.rules.append(StyleRule(
                        markdown_pattern=key,
                        css_selector=value_str,
                    ))
            except json.JSONDecodeError:
                pass  # 使用空映射
        
        return css_code, style_mapping
    
    def _extract_code_block(self, text: str, language: str) -> Optional[str]:
        """从响应中提取代码块"""
        import re
        pattern = rf"```{language}\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None
    
    def _save_assets(
        self, 
        state: AgentState, 
        css_code: str, 
        js_code: str, 
        style_mapping: StyleMapping
    ) -> AgentState:
        """保存设计资产到工作目录"""
        assets_dir = Path(state.workspace_path) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 CSS
        css_path = assets_dir / "style.css"
        css_path.write_text(css_code, encoding="utf-8")
        state.css_path = str(css_path)
        
        # 保存 JS
        js_path = assets_dir / "main.js"
        js_path.write_text(js_code, encoding="utf-8")
        state.js_path = str(js_path)
        
        # 保存 Style Mapping
        mapping_path = Path(state.workspace_path) / "style_mapping.json"
        mapping_path.write_text(
            style_mapping.model_dump_json(indent=2),
            encoding="utf-8"
        )
        state.style_mapping = style_mapping
        
        return state


def create_design_agent(client: Optional[GeminiClient] = None) -> DesignAgent:
    """创建设计组 Agent 实例"""
    return DesignAgent(client=client)
