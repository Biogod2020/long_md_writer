"""
Node 6: HTML Transformer Agent (全量上下文转换器)
约束性转换：严格遵守 Style Mapping
"""

from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import AgentState, SectionInfo


TRANSFORMER_SYSTEM_PROMPT = """You are an expert HTML transformer. Your task is to convert Markdown content into high-quality semantic HTML fragments.

### Core Rules
1. **Strict Style Mapping**: You MUST use the class names defined in `style_mapping.json`. Do not invent your own classes.
2. **ID Uniqueness**: Ensure all element IDs within the fragment are unique and do not clash with previously used IDs.
3. **Fragment Only**: Output only the HTML content. Do NOT include `<html>`, `<head>`, or `<body>` tags.
4. **Semantic HTML**: Use semantic tags like `<article>`, `<section>`, `<aside>`, `<figure>`, and `<nav>` where appropriate.
5. **Accessibility**: Include `alt` text for images and `title` attributes for links.

### Special Block Conversion
- `:::important ... :::` -> Use the class mapped to `important_card` or similar in Style Mapping.
- `:::warning ... :::` -> Use the class mapped to `warning_callout` or similar in Style Mapping.
- `[REF:sec-id]` -> Convert to `<a href="#sec-id">...</a>`.
- Math formulas should remain as-is (they will be rendered by JS).

### Output
- Output ONLY the clean HTML fragment.
- Do NOT wrap the output in Markdown code blocks (```html).
- Ensure all tags are properly nested and closed.
"""


class TransformerAgent:
    """HTML 转换器 Agent"""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        转换单个章节为 HTML
        
        注意：此方法每次只转换一个章节，需要在工作流中循环调用
        """
        if not state.manifest or not state.style_mapping:
            state.errors.append("Transformer Agent: Manifest or StyleMapping not available")
            return state
        
        # 确定当前要转换的章节索引
        transform_index = len(state.completed_html_sections)
        
        if transform_index >= len(state.manifest.sections):
            # 所有章节已转换
            return state
        
        current_section = state.manifest.sections[transform_index]
        
        # 获取对应的 Markdown 文件
        if transform_index >= len(state.completed_md_sections):
            state.errors.append(f"Transformer Agent: Markdown for {current_section.id} not available")
            return state
        
        md_path = state.completed_md_sections[transform_index]
        
        try:
            md_content = Path(md_path).read_text(encoding="utf-8")
        except Exception as e:
            state.errors.append(f"Transformer Agent: Failed to read {md_path}: {e}")
            return state
        
        # 构建提示
        prompt = self._build_prompt(state, current_section, md_content)
        
        # 调用 Gemini (带重试逻辑)
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = self.client.generate(
                    prompt=prompt,
                    system_instruction=TRANSFORMER_SYSTEM_PROMPT,
                    temperature=0.3,
                    stream=True  # 启用流式生成以避免 500 SSL 超时
                )
                if response.success:
                    break
                else:
                    print(f"  [Transformer] Attempt {attempt+1} failed: {response.error}")
            except Exception as e:
                print(f"  [Transformer] Attempt {attempt+1} error: {e}")
            
            if attempt < max_retries - 1:
                import time
                time.sleep(2 * (attempt + 1)) # 指数退避
        
        if not response or not response.success:
            state.errors.append(f"Transformer Agent failed on {current_section.id} after {max_retries} attempts. Last error: {response.error if response else 'Unknown'}")
            return state
        
        # 保存 HTML 片段
        try:
            html_path = self._save_html(state, current_section, response.text)
            state.completed_html_sections.append(str(html_path))
        except Exception as e:
            state.errors.append(f"Failed to save HTML {current_section.id}: {str(e)}")
        
        return state
    
    def run_all(self, state: AgentState) -> AgentState:
        """转换所有章节（循环调用 run）"""
        while not state.all_sections_transformed():
            state = self.run(state)
            if state.errors:
                break
        return state
    
    def _build_prompt(self, state: AgentState, section: SectionInfo, md_content: str) -> str:
        """构建转换提示"""
        parts = []
        
        # 0. Technical Specification (Global Context)
        parts.append("# Technical Specification (Global Context)\n")
        parts.append(state.manifest.description + "\n\n")
        
        # 1. Style Mapping
        parts.append("# Style Mapping (MUST follow)\n")
        parts.append("```json\n")
        mapping_dict = state.style_mapping.to_dict()
        import json
        parts.append(json.dumps(mapping_dict, indent=2, ensure_ascii=False))
        parts.append("\n```\n\n")
        
        # 2. Existing IDs (to avoid collisions)
        existing_ids = self._collect_existing_ids(state)
        if existing_ids:
            parts.append("# Used IDs (DO NOT reuse)\n")
            parts.append(", ".join(existing_ids))
            parts.append("\n\n")
        
        # 3. Design Assets Context (CSS + JS)
        # Include style.css for understanding available classes and design tokens
        if state.css_path:
            try:
                css_content = Path(state.css_path).read_text(encoding="utf-8")
                parts.append("# style.css (Available Classes & Design Tokens)\n")
                parts.append("Use ONLY these CSS classes and variables. Do NOT invent new class names.\n")
                parts.append(f"```css\n{css_content[:15000]}\n```\n\n")
            except Exception:
                pass
        
        # Include main.js for understanding interactive element contracts
        if state.js_path:
            try:
                js_content = Path(state.js_path).read_text(encoding="utf-8")
                parts.append("# main.js (Interactive Element Contracts)\n")
                parts.append("Ensure generated HTML elements match the selectors/IDs expected by this JavaScript.\n")
                parts.append(f"```javascript\n{js_content[:8000]}\n```\n\n")
            except Exception:
                pass
        
        # 4. ALL Previously converted HTML sections (for consistency)
        if state.completed_html_sections:
            parts.append("# Previously Converted HTML Sections (for style consistency)\n")
            parts.append("Match the structural patterns, class usage, and styling approach of these sections.\n\n")
            
            # Include all previous sections, with smart truncation for earlier ones
            total_sections = len(state.completed_html_sections)
            for idx, html_path in enumerate(state.completed_html_sections):
                try:
                    content = Path(html_path).read_text(encoding="utf-8")
                    section_name = Path(html_path).stem
                    
                    # More recent sections get more content shown
                    if idx >= total_sections - 2:
                        # Last 2 sections: show full content (up to 5000 chars)
                        truncated = content[:5000]
                        if len(content) > 5000:
                            truncated += "\n<!-- ... truncated ... -->"
                    elif idx >= total_sections - 4:
                        # Previous 2-4 sections: show 2000 chars
                        truncated = content[:2000]
                        if len(content) > 2000:
                            truncated += "\n<!-- ... truncated ... -->"
                    else:
                        # Earlier sections: show only structure (1000 chars)
                        truncated = content[:1000]
                        if len(content) > 1000:
                            truncated += "\n<!-- ... see full file for complete content ... -->"
                    
                    parts.append(f"## {section_name}\n```html\n{truncated}\n```\n\n")
                except Exception:
                    pass
        
        # 4. Current section info
        parts.append(f"# Current Section: {section.id}\n")
        parts.append(f"Section Title: {section.title}\n")
        if hasattr(section, 'metadata') and section.metadata:
            parts.append(f"Section Metadata (Layout/Context): {json.dumps(section.metadata)}\n")
        parts.append("\n")
        
        # 5. Markdown content
        parts.append("# Markdown Content\n")
        parts.append(md_content)
        parts.append("\n\n")
        
        # 6. SVG Handling (INLINE GENERATION)
        parts.append("# SVG Handling (GENERATE INLINE)\n")
        parts.append("For diagrams, flowcharts, concept maps, data visualizations, and schematics:\n")
        parts.append("- Generate COMPLETE, SELF-CONTAINED inline `<svg>` code directly in the HTML.\n")
        parts.append("- Use `viewBox` for responsiveness. Set `width='100%'`.\n")
        parts.append("- Apply colors from Style Mapping (use CSS variables if defined).\n")
        parts.append("- Include internal `<style>` if needed for animations.\n")
        parts.append("- Wrap in `<figure class='svg-container'><svg>...</svg><figcaption>Caption</figcaption></figure>`.\n\n")

        # 7. Image Handling (PLACEHOLDERS for Real Photos)
        parts.append("# Image Handling (PLACEHOLDERS)\n")
        parts.append("For real-world photographs, medical imagery, product photos, historical images, screenshots:\n")
        parts.append("- Do NOT use `<img>` tags with external URLs.\n")
        parts.append("- Generate a placeholder using this exact structure:\n")
        parts.append('```html\n<div class="img-placeholder" data-img-id="unique-semantic-id">\n')
        parts.append('  <p class="img-description">\n')
        parts.append('    Detailed description (50-200 words): Subject, Setting, Mood, Key Visual Elements.\n')
        parts.append('    Write in the article language.\n')
        parts.append('  </p>\n')
        parts.append("</div>\n```\n")
        parts.append("The ImageSourcingAgent will later find and replace these with real images.\n\n")
        
        parts.append("Convert the Markdown to HTML. Follow Style Mapping strictly, generate inline SVG for diagrams, and use img-placeholder for real photographs.")
        
        return "".join(parts)
    
    def _collect_existing_ids(self, state: AgentState) -> list[str]:
        """收集已转换 HTML 中使用的所有 ID"""
        import re
        ids = []
        
        for html_path in state.completed_html_sections:
            try:
                content = Path(html_path).read_text(encoding="utf-8")
                # 匹配所有 id="xxx" 或 id='xxx'
                matches = re.findall(r'id=["\']([^"\']+)["\']', content)
                ids.extend(matches)
            except Exception:
                pass
        
        return ids
    
    def _save_html(self, state: AgentState, section: SectionInfo, html_content: str) -> Path:
        """保存 HTML 片段到工作目录"""
        html_dir = Path(state.workspace_path) / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = html_dir / f"{section.id}.html"
        
        # 清理可能的代码块标记
        cleaned = html_content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        
        # 包装为带 ID 的 section
        wrapped = f'<section id="{section.id}" class="content-section">\n{cleaned}\n</section>'
        
        file_path.write_text(wrapped, encoding="utf-8")
        return file_path


def create_transformer_agent(client: Optional[GeminiClient] = None) -> TransformerAgent:
    """创建转换器 Agent 实例"""
    return TransformerAgent(client=client)
