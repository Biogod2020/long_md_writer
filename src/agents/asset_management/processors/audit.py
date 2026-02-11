"""
Audit Processor

Handles visual and code-based auditing of assets.
"""

import re
import json
import base64
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from ....core.gemini_client import GeminiClient
from ....core.types import AgentState


VISUAL_AUDIT_PROMPT = """You are a senior visual editor and content auditor. Your task is to evaluate this image against its intended purpose with high precision.

## Intent Description
{intent_description}

## Standardized Scoring Rubric (0-100)

1. **Information Accuracy (40%)**:
   - Does the image correctly represent the intended information?
   - Deduct for factual errors, misleading elements, or missed requirements.

2. **Visual Clarity & Composition (30%)**:
   - Is the content clear and easy to understand at a glance?
   - Check contrast, balance, and focus. Deduct for clutter or poor legibility.

3. **Professional Quality (30%)**:
   - Check for professional aesthetics, consistent styling, and high-fidelity output.
   - Deduct for low resolution, artifacts, or an unprofessional "primitive" feel.

## Performance Mapping
- 90-100: pass | Exceptional, ready for premium publication.
- 80-89: pass | High quality, meets all core requirements.
- 65-79: needs_revision | Functional but requires specific refinements.
- <65: fail | Significant quality or accuracy issues.

## Output (JSON only)
```json
{{
  "accuracy_score": 0,
  "clarity_score": 0,
  "quality_score": 0,
  "overall_score": 0,
  "result": "pass|fail|needs_revision",
  "issues": [],
  "suggestions": [],
  "quality_assessment": "Summary of pros and cons."
}}
```
"""

SVG_AUDIT_PROMPT = """You are a senior SVG technical auditor. Evaluate the provided code against technical and visual standards.

## Intent Description
{intent_description}

## SVG Code
```svg
{svg_code}
```

## Standardized Scoring Rubric (0-100)

1. **Information Integrity (40%)**:
   - Does the SVG accurately convey the intended information?
2. **Code Quality & Technicality (30%)**:
   - Check for efficient path usage, semantic grouping (<g>), responsiveness (viewBox), and valid XML.
3. **Visual Clarity (30%)**:
   - Evaluate layout, text legibility, and appropriate use of strokes and colors.

## Performance Mapping
- 90-100: pass | Textbook quality, efficient code.
- 80-89: pass | Meets professional standards.
- 65-79: needs_revision | Functional but lacks polish or technical optimization.
- <65: fail | Inaccurate or technically broken.

## Output (JSON only)
```json
{{
  "integrity_score": 0,
  "code_score": 0,
  "visual_score": 0,
  "overall_score": 0,
  "result": "pass|fail|needs_revision",
  "issues": [],
  "suggestions": [],
  "quality_assessment": "Summary of findings."
}}
```
"""


def check_svg_syntax(svg_code: str) -> list[str]:
    """检查 SVG 基本语法"""
    issues = []
    if not re.search(r'<svg[^>]*>', svg_code, re.IGNORECASE):
        issues.append("Missing <svg> open tag")
    if not re.search(r'</svg>', svg_code, re.IGNORECASE):
        issues.append("Missing </svg> close tag")
    if '<svg' in svg_code and 'xmlns' not in svg_code:
        issues.append("Missing xmlns declaration")
    return issues


def extract_json_payload(text: str) -> Optional[str]:
    """提取 JSON 响应内容"""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        return json_match.group(0)
    return None


async def audit_image_async(
    client: GeminiClient,
    image_path: Path,
    intent_description: str
) -> Optional[Dict[str, Any]]:
    """异步审计图片资产"""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = image_path.suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }.get(ext, "image/png")

    prompt = VISUAL_AUDIT_PROMPT.format(intent_description=intent_description)
    parts = [
        {"text": prompt},
        {"inlineData": {"mimeType": mime_type, "data": image_data}}
    ]

    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="You are a visual content auditor. Output JSON only.",
            stream=True
        )
        if not response.success:
            return None

        payload = extract_json_payload(response.text)
        return json.loads(payload) if payload else None
    except Exception:
        return None


async def audit_svg_async(
    client: GeminiClient,
    svg_code: str,
    intent_description: str
) -> Optional[Dict[str, Any]]:
    """异步审计 SVG 资产 (纯代码分析，回退模式)"""
    prompt = SVG_AUDIT_PROMPT.format(
        intent_description=intent_description,
        svg_code=svg_code
    )
    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="You are an SVG auditor. Output JSON only.",
            stream=True
        )
        if not response.success:
            return None

        payload = extract_json_payload(response.text)
        return json.loads(payload) if payload else None
    except Exception:
        return None


# ============================================================================
# SVG 渲染与视觉审计 (SOTA 2.0 双路交叉验证)
# ============================================================================

SVG_VISUAL_AUDIT_PROMPT = """You are a Senior Executive Editor and Visual Quality Lead. Your mission is to evaluate if this SVG asset achieves the SOTA standard for professional scientific documentation.

## Audit Philosophy: Functional Clarity over Mechanical Perfection
Do not act as a simple collision detector. Instead, use your expert judgment to answer: "Does this diagram effectively and professionally communicate the intended concept to a medical student based on the surrounding article context?"

## Evaluation Rubric (0-100)

1. **Analytical Accuracy (40%)**: Does the diagram correctly represent the scientific or anatomical mechanism described in the [ARTICLE CONTEXT]? Check labels, vector directions, and logical connections against the text.
2. **Pedagogical Effectiveness (30%)**: Is the information clear? Are labels positioned intuitively? A minor overlap is acceptable IF the text remains 100% legible and the meaning is unambiguous.
3. **Executive Aesthetic (30%)**: Does it look like a custom illustration from a premium journal (Nature, NEJM)? Evaluate the use of color harmony, line weights, and spatial balance.

## Decision Guidelines
- **PASS**: The diagram is professional, accurate, and perfectly aligned with the article's narrative. Minor spacing issues that don't hinder comprehension are ignored.
- **NEEDS_REVISION**: There are errors in scientific logic relative to the text, or severe clutter that makes the information difficult to parse.
- **FAIL**: Factual inaccuracies, broken rendering, or completely unprofessional layout.

## Output (JSON only)
```json
{{
  "thought": "Briefly explain your expert reasoning, focusing on consistency with the text context.",
  "accuracy_score": 0,
  "pedagogical_score": 0,
  "aesthetic_score": 0,
  "overall_score": 0,
  "result": "pass|fail|needs_revision",
  "issues": ["List only major problems"],
  "suggestions": ["Strategic advice for the illustrator"]
}}
```
"""


def render_svg_to_png_base64(svg_code: str, width: int = 1200) -> Optional[str]:
    """使用 cairosvg 将 SVG 渲染为 PNG (base64)"""
    try:
        import cairosvg
        png_data = cairosvg.svg2png(
            bytestring=svg_code.encode("utf-8"),
            output_width=width
        )
        return base64.b64encode(png_data).decode("utf-8")
    except ImportError:
        print("    [Audit] cairosvg not installed, trying browser render...")
        return None
    except Exception as e:
        print(f"    [Audit] cairosvg render failed: {e}")
        return None


async def render_svg_with_playwright(svg_code: str, output_path: Path) -> bool:
    """使用 Playwright 渲染 SVG 为 PNG (高保真，支持中文字体)"""
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            html, body {{ margin: 0; padding: 0; background: white; }}
            body {{ display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; }}
            svg {{ 
                display: block; 
                max-width: 100vw; 
                max-height: 100vh; 
                width: auto; 
                height: auto; 
                min-width: 200px; 
                min-height: 200px;
            }}
        </style>
    </head>
    <body>
        {svg_code}
    </body>
    </html>
    """
    temp_html = output_path.with_suffix(".html")
    temp_html.write_text(html_template, encoding="utf-8")
    
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Use a more reasonable viewport
            context = await browser.new_context(viewport={"width": 1000, "height": 800})
            page = await context.new_page()
            await page.goto(f"file://{temp_html.absolute()}", wait_until="networkidle")
            await asyncio.sleep(0.5)
            
            # Take screenshot
            await page.screenshot(path=str(output_path), full_page=False)
            
            # Post-process: Resize and compress using PIL to reduce payload
            from PIL import Image
            with Image.open(output_path) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                # If width > 1024, resize
                if img.width > 1024:
                    ratio = 1024 / img.width
                    img = img.resize((1024, int(img.height * ratio)), Image.Resampling.LANCZOS)
                # Save back with compression
                img.save(output_path, format="JPEG", quality=80, optimize=True)
                
            return True
    except Exception as e:
        print(f"    [Audit] Playwright render failed: {e}")
        return False
    finally:
        if temp_html.exists():
            temp_html.unlink()


async def audit_svg_visual_async(
    client: GeminiClient,
    svg_code: str,
    intent_description: str,
    state: Optional[AgentState] = None,
    svg_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """双路交叉 SVG 审计：代码分析 + 渲染图视觉分析 (优先使用浏览器渲染以支持中文字体)"""
    import tempfile
    
    # Step 1: 优先尝试浏览器渲染 (Playwright) 以解决 CJK 字体问题
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    png_b64 = None
    if await render_svg_with_playwright(svg_code, tmp_path):
        try:
            with open(tmp_path, "rb") as f:
                png_b64 = base64.b64encode(f.read()).decode("utf-8")
        finally:
            tmp_path.unlink(missing_ok=True)
    
    # Step 2: 如果浏览器渲染失败，尝试 cairosvg
    if not png_b64:
        print("    [Audit] Browser render failed, trying cairosvg...")
        png_b64 = render_svg_to_png_base64(svg_code)
    
    # Step 3: 如果渲染均失败，回退到纯代码审计
    if not png_b64:
        print("    [Audit] All render methods failed, falling back to code-only audit")
        return await audit_svg_async(client, svg_code, intent_description)
    
    # Step 4: 多模态审计请求
    prompt = SVG_VISUAL_AUDIT_PROMPT.format(intent_description=intent_description)
    parts = [
        {"text": prompt},
        {"text": f"## SVG Source Code\n```svg\n{svg_code}\n```"},
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": png_b64
            }
        }
    ]
    
    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="You are an SVG auditor. Analyze both code and rendered image. Output JSON only.",
            stream=True
        )
        if not response.success:
            return None

        # Capture thoughts
        if state and response.thoughts:
            state.thoughts += f"\n[SVG Visual Audit] {response.thoughts}"

        payload = extract_json_payload(response.text)
        return json.loads(payload) if payload else None
    except Exception as e:
        print(f"    [Audit] Multi-modal audit failed: {e}")
        return None
