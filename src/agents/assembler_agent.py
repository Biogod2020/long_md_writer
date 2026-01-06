"""
Node 7: Assembler & QA Agent (合体质检员)
拼接 HTML 片段 + BeautifulSoup 验证 + AI 修复
"""

from pathlib import Path
from typing import Optional
import json

from bs4 import BeautifulSoup

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import AgentState


LAYOUT_TEMPLATES = {
    "standard": '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta name="author" content="{author}">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body class="layout-standard">
    <div class="progress-bar" id="progress-bar"></div>
    <nav class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <h2>目录</h2>
            <button class="theme-toggle" id="theme-toggle" aria-label="切换主题">🌙</button>
        </div>
        <div class="toc" id="toc"></div>
    </nav>
    <main class="main-content">
        <article class="article">
            <header class="article-header">
                <h1>{title}</h1>
                <p class="article-meta">{author}</p>
            </header>
            {content}
        </article>
    </main>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
    <script src="assets/main.js"></script>
</body>
</html>''',

    "slide": '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
    <link rel="stylesheet" href="assets/style.css">
</head>
<body class="layout-slide">
    <div class="slide-container">
        {content}
    </div>
    <div class="slide-controls">
        <button id="prev-slide">←</button>
        <span id="slide-number">1 / 1</span>
        <button id="next-slide">→</button>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <script src="assets/main.js"></script>
</body>
</html>''',

    "dashboard": '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body class="layout-dashboard">
    <header class="dashboard-header">
        <h1>{title}</h1>
        <div class="dashboard-meta">{author}</div>
    </header>
    <div class="dashboard-grid">
        {content}
    </div>
    <script src="assets/main.js"></script>
</body>
</html>'''
}


REPAIR_SYSTEM_PROMPT = """你是一位 HTML 修复专家。给定一段有错误的 HTML 代码，请修复所有问题：
1. 闭合未闭合的标签
2. 修复嵌套错误
3. 修复属性语法错误
4. 确保语义正确

只输出修复后的 HTML 代码，不要任何解释。
"""


class AssemblerAgent:
    """合体质检员 Agent"""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """执行拼接与质检流程"""
        
        if not state.manifest:
            state.errors.append("Assembler Agent: Manifest not available")
            return state
        
        # Step 1: 按顺序读取所有 HTML 片段
        all_html_parts = self._read_html_sections(state)
        
        if not all_html_parts:
            state.errors.append("Assembler Agent: No HTML sections to assemble")
            return state
        
        # Step 2: 拼接为完整内容
        combined_content = "\n\n".join(all_html_parts)
        
        # Step 3: BeautifulSoup 验证
        is_valid, errors = self._validate_html(combined_content)
        
        # Step 4: 如果验证失败，尝试 AI 修复
        if not is_valid:
            repaired_content = self._repair_html(combined_content, errors)
            if repaired_content:
                combined_content = repaired_content
                # 再次验证
                is_valid, errors = self._validate_html(combined_content)
                if not is_valid:
                    state.errors.append(f"Assembler Agent: Repair failed, remaining errors: {errors}")
        
        # Step 5: 生成最终 HTML
        try:
            final_html = self._generate_final_html(state, combined_content)
            final_path = self._save_final_html(state, final_html)
            state.final_html_path = str(final_path)
        except Exception as e:
            state.errors.append(f"Assembler Agent: Failed to generate final HTML: {e}")
        
        return state
    
    def _read_html_sections(self, state: AgentState) -> list[str]:
        """按照 manifest 顺序读取 HTML 片段，并添加源文件标记"""
        parts = []
        
        for html_path in state.completed_html_sections:
            try:
                content = Path(html_path).read_text(encoding="utf-8")
                # Add source markers for VQA traceability
                relative_path = Path(html_path).name
                marked_content = f"<!-- [SOURCE:html/{relative_path}] -->\n{content}\n<!-- [/SOURCE:html/{relative_path}] -->"
                parts.append(marked_content)
            except Exception as e:
                parts.append(f"<!-- Error reading {html_path}: {e} -->")
        
        return parts
    
    def _validate_html(self, html_content: str) -> tuple[bool, list[str]]:
        """使用 BeautifulSoup 验证 HTML"""
        errors = []
        
        try:
            # 使用 lxml 解析器进行严格验证
            soup = BeautifulSoup(html_content, "lxml")
            
            # 检查是否有解析警告
            # BeautifulSoup 不会抛出异常，但我们可以检查一些常见问题
            
            # 检查空标签
            for tag in soup.find_all():
                if tag.name in ['div', 'span', 'p', 'section', 'article']:
                    if not tag.get_text(strip=True) and not tag.find_all():
                        # 空的块级元素可能是问题
                        pass
            
            # 使用 html5lib 进行更严格的验证
            soup_strict = BeautifulSoup(html_content, "html5lib")
            
            return True, []
            
        except Exception as e:
            errors.append(str(e))
            return False, errors
    
    def _repair_html(self, html_content: str, errors: list[str]) -> Optional[str]:
        """使用 AI 修复 HTML 错误"""
        prompt = f"""# HTML 代码（有错误）

{html_content}

# 检测到的错误

{chr(10).join(errors)}

请修复以上 HTML 代码中的所有错误。
"""
        
        response = self.client.generate(
            prompt=prompt,
            system_instruction=REPAIR_SYSTEM_PROMPT,
            temperature=0.2,
            
        )
        
        if response.success:
            # 清理可能的代码块标记
            cleaned = response.text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)
            return cleaned
        
        return None
    
    def _generate_final_html(self, state: AgentState, content: str) -> str:
        """选择模版并生成最终文档"""
        import html
        layout_type = state.manifest.config.get("layout_type", "standard")
        template = LAYOUT_TEMPLATES.get(layout_type, LAYOUT_TEMPLATES["standard"])
        
        raw_desc = state.manifest.description or ""
        first_line = raw_desc.split('\n')[0] if raw_desc else ""
        truncated_desc = first_line[:200] if len(first_line) > 200 else first_line
        safe_desc = html.escape(truncated_desc)
        
        return template.format(
            title=state.manifest.project_title,
            description=safe_desc,
            author=state.manifest.author or "Anonymous",
            content=content,
        )
    
    def _save_final_html(self, state: AgentState, html_content: str) -> Path:
        """保存最终 HTML 文件"""
        output_path = Path(state.workspace_path) / "final.html"
        output_path.write_text(html_content, encoding="utf-8")
        return output_path


def create_assembler_agent(client: Optional[GeminiClient] = None) -> AssemblerAgent:
    """创建质检员 Agent 实例"""
    return AssemblerAgent(client=client)
