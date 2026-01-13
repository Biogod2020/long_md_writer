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


VISUAL_AUDIT_PROMPT = """你是一个专业的视觉内容审计员。请评估这张图片是否符合以下意图描述。

## 意图描述
{intent_description}

## 评估标准
1. **内容匹配度** (0-100分)
   - 图片是否准确表达了意图描述中的核心概念？
   - 关键元素是否都呈现？

2. **视觉质量** (0-100分)
   - 清晰度、对比度、配色是否合适？
   - 是否存在模糊、失真、水印等问题？

3. **教学适用性** (0-100分)
   - 是否适合用于教学/文档？
   - 标注、文字是否清晰易读？

## 输出格式
请严格按照以下 JSON 格式输出：

```json
{{
  "content_match_score": 85,
  "visual_quality_score": 90,
  "teaching_suitability_score": 80,
  "overall_score": 85,
  "result": "PASS|FAIL|NEEDS_REVISION",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "quality_assessment": "简短的质量总结"
}}
```

**评判标准**:
- overall_score >= 75: PASS
- overall_score >= 50: NEEDS_REVISION
- overall_score < 50: FAIL
"""

SVG_AUDIT_PROMPT = """你是一个专业的 SVG 图形审计员。请评估这段 SVG 代码是否符合以下意图描述。

## 意图描述
{intent_description}

## SVG 代码
```svg
{svg_code}
```

## 评估标准
1. **内容匹配度** (0-100分)
   - SVG 是否准确表达了意图描述中的核心概念？
   - 关键元素是否都呈现？

2. **代码质量** (0-100分)
   - SVG 语法是否正确？
   - 是否使用了合理的元素和属性？

3. **视觉效果** (0-100分)
   - 配色、布局是否合理？
   - 文字是否清晰可读？

## 输出格式
请严格按照以下 JSON 格式输出：

```json
{{
  "content_match_score": 85,
  "code_quality_score": 90,
  "visual_effect_score": 80,
  "overall_score": 85,
  "result": "PASS|FAIL|NEEDS_REVISION",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "quality_assessment": "简短的质量总结"
}}
```

**评判标准**:
- overall_score >= 75: PASS
- overall_score >= 50: NEEDS_REVISION
- overall_score < 50: FAIL
"""


def check_svg_syntax(svg_code: str) -> list[str]:
    """检查 SVG 基本语法"""
    issues = []
    if not re.search(r'<svg[^>]*>', svg_code, re.IGNORECASE):
        issues.append("缺少 <svg> 开始标签")
    if not re.search(r'</svg>', svg_code, re.IGNORECASE):
        issues.append("缺少 </svg> 结束标签")
    if '<svg' in svg_code and 'xmlns' not in svg_code:
        issues.append("缺少 xmlns 声明")
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
            system_instruction="你是一个专业的视觉内容审计员。请严格评估并输出 JSON 格式。"
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
            system_instruction="你是一个专业的 SVG 图形审计员。请严格评估并输出 JSON 格式。"
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

SVG_VISUAL_AUDIT_PROMPT = """你是一个专业的 SVG 图形审计员。你将同时看到 SVG 的**源代码**和**渲染后的图片**。

## 意图描述
{intent_description}

## 评估标准
1. **内容匹配度** (0-100分)
   - 渲染后的图形是否准确表达了意图描述中的核心概念？
   - 关键元素是否都呈现？

2. **视觉质量** (0-100分)
   - 布局是否合理？元素是否重叠？
   - 配色是否美观、对比度是否达标？
   - 文字是否清晰可读？

3. **代码质量** (0-100分)
   - SVG 语法是否规范？
   - 是否存在冗余代码？

## 输出格式
请严格按照以下 JSON 格式输出：

```json
{{
  "content_match_score": 85,
  "visual_quality_score": 90,
  "code_quality_score": 80,
  "overall_score": 85,
  "result": "PASS|FAIL|NEEDS_REVISION",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "quality_assessment": "简短的质量总结"
}}
```

**评判标准**:
- overall_score >= 75: PASS
- overall_score >= 50: NEEDS_REVISION
- overall_score < 50: FAIL
"""


def render_svg_to_png_base64(svg_code: str, width: int = 1200) -> Optional[str]:
    """
    使用 cairosvg 将 SVG 渲染为 PNG (base64)
    
    Args:
        svg_code: SVG 源代码
        width: 输出宽度 (高度自动计算)
    
    Returns:
        Base64 编码的 PNG 数据，失败返回 None
    """
    try:
        import cairosvg
        png_data = cairosvg.svg2png(
            bytestring=svg_code.encode("utf-8"),
            output_width=width
        )
        return base64.b64encode(png_data).decode("utf-8")
    except ImportError:
        print("    [Audit] cairosvg 未安装，尝试浏览器渲染...")
        return None
    except Exception as e:
        print(f"    [Audit] cairosvg 渲染失败: {e}")
        return None


def render_svg_with_browser(svg_path: Path, output_path: Path) -> bool:
    """
    使用 DrissionPage 渲染 SVG 为 PNG (高保真)
    
    Args:
        svg_path: SVG 文件路径
        output_path: 输出 PNG 路径
    
    Returns:
        是否成功
    """
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
        
        co = ChromiumOptions()
        co.auto_port()
        co.headless()
        co.set_argument("--force-device-scale-factor=2")  # 高清渲染
        co.set_argument("--disable-gpu")
        co.set_argument("--no-sandbox")
        
        page = ChromiumPage(co)
        try:
            page.get(f"file://{svg_path.absolute()}")
            page.wait(0.5)  # 等待渲染完成
            page.get_screenshot(path=str(output_path))
            return True
        finally:
            page.quit()
    except Exception as e:
        print(f"    [Audit] 浏览器渲染失败: {e}")
        return False


async def audit_svg_visual_async(
    client: GeminiClient,
    svg_code: str,
    intent_description: str,
    svg_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    双路交叉 SVG 审计：代码分析 + 渲染图视觉分析
    
    Args:
        client: Gemini 客户端
        svg_code: SVG 源代码
        intent_description: 原始意图描述
        svg_path: SVG 文件路径 (用于浏览器渲染回退)
    
    Returns:
        审计结果字典，失败返回 None
    """
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
        print("    [Audit] 渲染失败，回退到纯代码审计模式")
        return await audit_svg_async(client, svg_code, intent_description)
    
    # Step 4: 多模态审计请求
    prompt = SVG_VISUAL_AUDIT_PROMPT.format(intent_description=intent_description)
    parts = [
        {"text": prompt},
        {"text": f"## SVG 源代码\n```svg\n{svg_code[:8000]}\n```"},  # 限制代码长度
        {"inlineData": {"mimeType": "image/png", "data": png_b64}}
    ]
    
    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="你是一个专业的 SVG 图形审计员。请同时分析代码和渲染图，严格评估并输出 JSON 格式。"
        )
        if not response.success:
            return None

        payload = extract_json_payload(response.text)
        return json.loads(payload) if payload else None
    except Exception as e:
        print(f"    [Audit] 多模态审计失败: {e}")
        return None
