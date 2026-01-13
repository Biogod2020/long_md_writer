"""
Audit Processor

Handles visual and code-based auditing of assets.
"""

import re
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any

from ....core.gemini_client import GeminiClient


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
            system_instruction="You are a visual content auditor. Output JSON only."
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
            system_instruction="You are an SVG auditor. Output JSON only."
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

SVG_VISUAL_AUDIT_PROMPT = """You are a senior supervisor of visual quality and technical accuracy. Audit this SVG asset based on its source code AND rendered output. 

## Intent Description
{intent_description}

## CRITICAL: Zero Tolerance Collision Policy
- **NO OVERLAPS**: If any text label touches or overlaps with a path, shape, or arrow, you MUST penalize the "Legibility & Clarity" score to ZERO.
- **Breathing Room**: Labels must have at least 10px of negative space around them.
- **Visual Artifacts**: Any messy lines or clashing elements should be strictly flagged.

## Scoring Rubric (0-100)

1. **Analytical Accuracy (40%)**: Correctness of the technical/anatomical information.
2. **Visual Design & Elegance (30%)**: Composition, line weights, color harmony, and professional finish.
3. **Legibility & Clarity (30%)**: ABSOLUTE isolation of text labels. **If overlaps exist, this score is 0.**

## Performance Mapping
- 90-100: pass | Perfect, publication-ready.
- 85-89: pass | High quality, but very minor aesthetic suggestions possible.
- 70-84: needs_revision | Functional but has visual flaws like tight spacing or poor hierarchy.
- <70: fail | Contains collisions, inaccuracies, or poor design.

## Output (JSON only)
```json
{{
  "collision_detected": true/false,
  "accuracy_score": 0,
  "design_score": 0,
  "clarity_score": 0,
  "overall_score": 0,
  "result": "pass|fail|needs_revision",
  "issues": [],
  "suggestions": [],
  "quality_assessment": "Summary of findings."
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


def render_svg_with_browser(svg_path: Path, output_path: Path) -> bool:
    """使用 DrissionPage 渲染 SVG 为 PNG (高保真)"""
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
        
        co = ChromiumOptions()
        co.auto_port()
        co.headless()
        co.set_argument("--force-device-scale-factor=2")
        co.set_argument("--disable-gpu")
        co.set_argument("--no-sandbox")
        
        page = ChromiumPage(co)
        try:
            page.get(f"file://{svg_path.absolute()}")
            page.wait(0.5)
            page.get_screenshot(path=str(output_path))
            return True
        finally:
            page.quit()
    except Exception as e:
        print(f"    [Audit] Browser render failed: {e}")
        return False


async def audit_svg_visual_async(
    client: GeminiClient,
    svg_code: str,
    intent_description: str,
    svg_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """双路交叉 SVG 审计：代码分析 + 渲染图视觉分析"""
    import tempfile
    
    # Step 1: 尝试 cairosvg 渲染
    png_b64 = render_svg_to_png_base64(svg_code)
    
    # Step 2: 如果失败，尝试浏览器渲染
    if not png_b64 and svg_path and svg_path.exists():
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        if render_svg_with_browser(svg_path, tmp_path):
            try:
                with open(tmp_path, "rb") as f:
                    png_b64 = base64.b64encode(f.read()).decode("utf-8")
            finally:
                tmp_path.unlink(missing_ok=True)
    
    # Step 3: 如果渲染失败，回退到纯代码审计
    if not png_b64:
        print("    [Audit] Render failed, falling back to code-only audit")
        return await audit_svg_async(client, svg_code, intent_description)
    
    # Step 4: 多模态审计请求
    prompt = SVG_VISUAL_AUDIT_PROMPT.format(intent_description=intent_description)
    parts = [
        {"text": prompt},
        {"text": f"## SVG Source Code\n```svg\n{svg_code[:8000]}\n```"},
        {"inlineData": {"mimeType": "image/png", "data": png_b64}}
    ]
    
    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="You are an SVG auditor. Analyze both code and rendered image. Output JSON only."
        )
        if not response.success:
            return None

        payload = extract_json_payload(response.text)
        return json.loads(payload) if payload else None
    except Exception as e:
        print(f"    [Audit] Multi-modal audit failed: {e}")
        return None
