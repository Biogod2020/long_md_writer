#!/usr/bin/env python3
"""
手动将 Markdown 转换为 HTML 并拼接成最终文档
"""

import re
from pathlib import Path
import markdown

# 配置
WORKSPACE = Path("workspace/ecg_lecture/ecg_v3")
MD_DIR = WORKSPACE / "md"
ASSETS_DIR = WORKSPACE / "assets"
OUTPUT_FILE = WORKSPACE / "final.html"

# 读取资产
css_content = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
js_content = (ASSETS_DIR / "main.js").read_text(encoding="utf-8")

# 读取所有 Markdown
sections = []
for i in range(1, 5):
    md_file = MD_DIR / f"sec-{i}.md"
    content = md_file.read_text(encoding="utf-8")
    sections.append((f"sec-{i}", content))

# 预处理 Markdown
def preprocess_md(content: str) -> str:
    """处理自定义标记"""
    # 处理 :::important ... :::
    content = re.sub(
        r':::important\s*(.*?)\s*:::',
        r'<div class="callout callout-important"><strong>💡 核心要点</strong>\n\1</div>',
        content, flags=re.DOTALL
    )
    # 处理 :::warning ... :::
    content = re.sub(
        r':::warning\s*(.*?)\s*:::',
        r'<div class="callout callout-warning"><strong>⚠️ 临床警示</strong>\n\1</div>',
        content, flags=re.DOTALL
    )
    # 处理内部引用 [REF:sec-X]
    content = re.sub(
        r'\[REF:(sec-\d+)\]',
        r'<a href="#\1" class="internal-ref">[\1]</a>',
        content
    )
    return content

# 转换 Markdown 为 HTML
md_converter = markdown.Markdown(
    extensions=['tables', 'fenced_code', 'codehilite', 'toc', 'md_in_html'],
    extension_configs={
        'codehilite': {'css_class': 'code-block'},
    }
)

html_sections = []
for sec_id, content in sections:
    processed = preprocess_md(content)
    html = md_converter.convert(processed)
    md_converter.reset()
    html_sections.append(f'<section id="{sec_id}" class="content-section">\n{html}\n</section>')

content_html = "\n\n".join(html_sections)

# 生成最终 HTML
final_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>从原理理解心电图 - 10000字深度讲义</title>
    <meta name="description" content="本讲义从电生理底层逻辑到临床诊断，彻底拆解心电图的底层原理。">
    
    <!-- KaTeX for math -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
    
    <!-- Prism.js for code -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet">
    
    <style>
{css_content}

/* 额外样式 */
.callout {{
    padding: 1.5rem;
    margin: 1.5rem 0;
    border-radius: 8px;
    border-left: 4px solid;
}}
.callout-important {{
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(59, 130, 246, 0.05));
    border-color: #3b82f6;
}}
.callout-warning {{
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(245, 158, 11, 0.05));
    border-color: #f59e0b;
}}
.internal-ref {{
    color: #3b82f6;
    text-decoration: none;
    font-weight: 500;
}}
.internal-ref:hover {{
    text-decoration: underline;
}}
.content-section {{
    margin-bottom: 3rem;
    padding-bottom: 2rem;
    border-bottom: 1px solid var(--border-color, #e5e7eb);
}}
    </style>
</head>
<body>
    <div class="progress-bar" id="progress-bar"></div>
    
    <main class="main-content">
        <article class="article">
            <header class="article-header">
                <h1>从原理理解心电图</h1>
                <p class="article-subtitle">10000字深度讲义</p>
            </header>
            
            {content_html}
            
        </article>
    </main>
    
    <!-- KaTeX -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
    
    <!-- Prism.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    
    <script>
{js_content}

// 渲染数学公式
document.addEventListener("DOMContentLoaded", function() {{
    renderMathInElement(document.body, {{
        delimiters: [
            {{left: "$$", right: "$$", display: true}},
            {{left: "$", right: "$", display: false}},
            {{left: "\\\\[", right: "\\\\]", display: true}},
            {{left: "\\\\(", right: "\\\\)", display: false}}
        ]
    }});
}});
    </script>
</body>
</html>
'''

# 写入文件
OUTPUT_FILE.write_text(final_html, encoding="utf-8")
print(f"✓ 已生成: {OUTPUT_FILE}")
print(f"  文件大小: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
