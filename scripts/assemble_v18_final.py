#!/usr/bin/env python3
import re
import sys
from pathlib import Path
import markdown

def assemble_workspace(workspace_dir: str):
    ws_path = Path(workspace_dir)
    md_dir = ws_path / "md"
    resource_dir = ws_path / "resource"
    output_file = ws_path / "v18_publication.html"

    if not ws_path.exists():
        print(f"❌ Workspace not found: {ws_path}")
        return

    # Try to read CSS/JS
    css_content = ""
    js_content = ""
    css_path = resource_dir / "style.css"
    js_path = resource_dir / "main.js"
    
    if css_path.exists(): css_content = css_path.read_text(encoding="utf-8")
    if js_path.exists(): js_content = js_path.read_text(encoding="utf-8")

    # Discover Markdown sections
    md_files = sorted(list(md_dir.glob("*.md")))
    if not md_files:
        print(f"❌ No markdown files found in {md_dir}")
        return

    print(f"📖 Found {len(md_files)} sections. Assembling...")

    # Preprocessing
    def preprocess_md(content: str) -> str:
        # Use raw strings and handle multi-line replacements safely
        content = re.sub(r':::important\s*(.*?)\s*:::', r'<div class="callout callout-important"><strong>💡 核心要点</strong><br>\1</div>', content, flags=re.DOTALL)
        content = re.sub(r':::tip\s*(.*?)\s*:::', r'<div class="callout callout-tip"><strong>💡 专家提示</strong><br>\1</div>', content, flags=re.DOTALL)
        content = re.sub(r':::warning\s*(.*?)\s*:::', r'<div class="callout callout-warning"><strong>⚠️ 临床警示</strong><br>\1</div>', content, flags=re.DOTALL)
        return content

    md_converter = markdown.Markdown(extensions=['tables', 'fenced_code', 'codehilite', 'toc', 'md_in_html'])
    
    html_sections = []
    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        processed = preprocess_md(content)
        html = md_converter.convert(processed)
        md_converter.reset()
        html_sections.append(f'<section id="{md_path.stem}" class="content-section">\n{html}\n</section>')

    content_html = "\n\n".join(html_sections)

    final_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Magnum Opus 2.1 - v18 Publication</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet">
    <style>
{css_content}
.callout {{ padding: 1.5rem; margin: 1.5rem 0; border-radius: 8px; border-left: 4px solid; line-height: 1.6; }}
.callout-important {{ background: rgba(59, 130, 246, 0.1); border-color: #3b82f6; }}
.callout-tip {{ background: rgba(16, 185, 129, 0.1); border-color: #10b981; }}
.callout-warning {{ background: rgba(245, 158, 11, 0.1); border-color: #f59e0b; }}
.content-section {{ margin-bottom: 3rem; padding-bottom: 2rem; border-bottom: 1px solid #e5e7eb; }}
img {{ max-width: 100%; height: auto; display: block; margin: 1rem auto; border-radius: 4px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
figure {{ margin: 2rem 0; text-align: center; }}
figcaption {{ margin-top: 0.75rem; font-size: 0.9rem; color: #6b7280; font-style: italic; }}
    </style>
</head>
<body>
    <main class="main-content">
        <article class="article">
            {content_html}
        </article>
    </main>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
    <script>
{js_content}
document.addEventListener("DOMContentLoaded", function() {{
    renderMathInElement(document.body, {{
        delimiters: [
            {{left: "$$", right: "$$", display: true}},
            {{left: "$", right: "$", display: false}}
        ]
    }});
}});
    </script>
</body>
</html>'''

    output_file.write_text(final_html, encoding="utf-8")
    print(f"✅ Assembly complete: {output_file.absolute()}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python assemble_v18_final.py <workspace_dir>")
    else:
        assemble_workspace(sys.argv[1])
