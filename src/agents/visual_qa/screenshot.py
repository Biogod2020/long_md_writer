"""Screenshot capture logic for Visual QA."""

import io
from pathlib import Path
from typing import List, Optional
from DrissionPage import ChromiumOptions, ChromiumPage

def take_screenshots(
    html_path: Path, 
    workspace_path: str, 
    headless: bool = True,
    debug: bool = False
) -> List[Path]:
    """
    Capture multiple overlapping screenshots of an HTML page.
    
    Returns a list of screenshot file paths.
    """
    screenshot_paths = []
    assets_dir = Path(workspace_path) / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    VIEWPORT_WIDTH = 1200
    VIEWPORT_HEIGHT = 1000
    OVERLAP = 200
    EFFECTIVE_HEIGHT = VIEWPORT_HEIGHT - OVERLAP
    
    try:
        co = ChromiumOptions()
        co.auto_port()
        if headless:
            co.headless()
        co.set_argument('--window-size', f'{VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}')
        co.set_argument('--disable-gpu')
        co.set_argument('--no-sandbox')
        
        page = ChromiumPage(co)
        page.get(f"file://{html_path.absolute()}")
        page.wait(2)
        
        total_height = page.run_js("return document.body.scrollHeight")
        num_screenshots = min(8, (total_height + EFFECTIVE_HEIGHT - 1) // EFFECTIVE_HEIGHT)
        
        if debug:
            print(f"    [Screenshot] Height: {total_height}px, taking {num_screenshots} parts.")
        
        for i in range(num_screenshots):
            scroll_y = i * EFFECTIVE_HEIGHT
            page.run_js(f"window.scrollTo(0, {scroll_y})")
            
            # Inject visual watermark
            mark_js = f"""
            (function() {{
                let old = document.getElementById('vqa-marker');
                if (old) old.remove();
                let div = document.createElement('div');
                div.id = 'vqa-marker';
                div.style.cssText = 'position:fixed;top:10px;right:10px;background:rgba(255,0,0,0.8);color:white;padding:5px 15px;z-index:999999;border-radius:20px;font-family:monospace;font-size:14px;font-weight:bold;box-shadow:0 2px 10px rgba(0,0,0,0.5)';
                div.innerText = 'PART {i+1} | Scroll: {scroll_y}px';
                document.body.appendChild(div);
            }})();
            """
            page.run_js(mark_js)
            page.wait(0.4)
            
            screen_path = assets_dir / f"vqa_{html_path.stem}_p{i+1}.jpg"
            page.get_screenshot(path=str(screen_path))
            
            # Compress with PIL
            try:
                from PIL import Image
                with Image.open(screen_path) as img:
                    img = img.convert('RGB')
                    img.save(screen_path, format="JPEG", quality=80, optimize=True)
            except: 
                pass
            
            screenshot_paths.append(screen_path)
        
        page.quit()
        
    except Exception as e:
        print(f"    [Screenshot] Error: {e}")
    
    return screenshot_paths

def prepare_section_preview(
    section_path: str,
    workspace_path: str,
    html_template: str
) -> Optional[Path]:
    """
    Create a temporary full HTML page for a single section.
    """
    try:
        workspace = Path(workspace_path)
        section_content = Path(section_path).read_text(encoding="utf-8")
        
        css_content = ""
        css_path = workspace / "assets" / "style.css"
        if css_path.exists():
            css_content = css_path.read_text(encoding="utf-8")
        
        js_content = ""
        js_path = workspace / "assets" / "main.js"
        if js_path.exists():
            js_content = js_path.read_text(encoding="utf-8")
        
        # Build minimal HTML
        test_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VQA Test</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <style>{css_content}</style>
</head>
<body>
    <main class="main-content">
        {section_content}
    </main>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            if (typeof renderMathInElement !== 'undefined') {{
                renderMathInElement(document.body, {{
                    delimiters: [
                        {{left: "$$", right: "$$", display: true}},
                        {{left: "$", right: "$", display: false}}
                    ]
                }});
            }}
        }});
    </script>
    <script>{js_content}</script>
</body>
</html>"""
        
        temp_path = workspace / f"temp_vqa_{Path(section_path).stem}.html"
        temp_path.write_text(test_html, encoding="utf-8")
        return temp_path
        
    except Exception as e:
        print(f"    [Preview] Error creating preview: {e}")
        return None
