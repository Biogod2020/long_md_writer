"""
Vision Processor

Handles image analysis and semantic tagging using Vision API.
"""

import re
import json
import base64
from pathlib import Path
from typing import Optional

from ....core.gemini_client import GeminiClient
from ....core.types import AssetQualityLevel


VISION_TAGGING_PROMPT = """You are a professional visual content analyst and quality evaluator. Please analyze this image and provide the following information in a structured format:

## Required Information

1. **semantic_label**: A concise, professional English description of the core content. Use it for semantic matching.
   - Format: Noun phrase + detailed context.
   - Professional Examples:
     - "Conceptual illustration of a futuristic smart city with sustainable energy infrastructure"
     - "Atmospheric landscape photography of a misty pine forest at sunrise"
     - "Detailed technical blueprint of a high-performance turbofan engine"
     - "Vibrant infographic presenting global technology adoption trends from 2000 to 2025"
     - "High-speed photography of a water drop impacting a still surface, capturing crown formation"
     - "Minimalist UI design mockup for a mobile finance application in light mode"
     - "Abstract oil painting exploring color theory and geometric patterns"

2. **tags**: Provide 3-5 descriptive keywords (lowercase).
   - Examples: ["architecture", "technology", "nature", "infographic", "abstract"]

3. **quality_level**: Evaluate the visual quality.
   - HIGH: Professional, clear, no watermarks, suitable for high-end publication.
   - MEDIUM: Decent quality, minor artifacts, but clear enough for general use.
   - LOW: Blurred, watermarked, low resolution, or unprofessional.

4. **quality_notes**: Brief explanation of the quality assessment.

## Optional Information

5. **suitable_for**: List of recommended use cases (e.g., ["Conceptual Explanation", "Technical Manual", "Patient Education"]).

6. **unsuitable_for**: List of cases where this image might be misleading or inappropriate.

7. **suggested_focus**: Description of the primary visual focal point.

Please output strictly in JSON format:
```json
{
  "semantic_label": "...",
  "tags": ["tag1", "tag2", "tag3"],
  "quality_level": "HIGH|MEDIUM|LOW",
  "quality_notes": "...",
  "suitable_for": ["...", "..."],
  "unsuitable_for": ["..."],
  "suggested_focus": "..."
}
```

**Constraint**: Be strictly objective with quality. High-quality output is paramount for professional documentation.
"""


# MIME 类型映射
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
}


def _get_default_result(image_path: Path) -> dict:
    """生成默认分析结果"""
    return {
        "semantic_label": f"Image: {image_path.stem}",
        "tags": [image_path.stem.lower()],
        "quality_level": AssetQualityLevel.UNASSESSED,
        "quality_notes": None,
        "suitable_for": [],
        "unsuitable_for": [],
        "suggested_focus": None,
    }


def _parse_vision_response(text: str, default_result: dict) -> dict:
    """解析 Vision API 响应"""
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group())

        # 解析质量等级
        quality_str = data.get("quality_level", "UNASSESSED").upper()
        quality_level = {
            "HIGH": AssetQualityLevel.HIGH,
            "MEDIUM": AssetQualityLevel.MEDIUM,
            "LOW": AssetQualityLevel.LOW,
        }.get(quality_str, AssetQualityLevel.UNASSESSED)

        return {
            "semantic_label": data.get("semantic_label", default_result["semantic_label"]),
            "tags": data.get("tags", default_result["tags"]),
            "quality_level": quality_level,
            "quality_notes": data.get("quality_notes"),
            "suitable_for": data.get("suitable_for", []),
            "unsuitable_for": data.get("unsuitable_for", []),
            "suggested_focus": data.get("suggested_focus"),
        }
    return default_result


def analyze_image(client: GeminiClient, image_path: Path) -> dict:
    """
    使用 Vision API 分析图片

    Args:
        client: Gemini API 客户端
        image_path: 图片文件路径

    Returns:
        包含语义描述、标签、质量等级等的字典
    """
    default_result = _get_default_result(image_path)

    # 读取图片并编码为 base64
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # 确定 MIME 类型
    ext = image_path.suffix.lower()
    mime_type = MIME_TYPES.get(ext, "image/png")

    # 构建多模态请求
    parts = [
        {"text": VISION_TAGGING_PROMPT},
        {"inlineData": {"mimeType": mime_type, "data": image_data}},
    ]

    try:
        response = client.generate(
            parts=parts,
            system_instruction="You are a professional visual content analyst and quality evaluator. Please output in JSON format strictly."
        )
        return _parse_vision_response(response.text, default_result)

    except Exception as e:
        print(f"[Vision Processor] Analysis failed: {e}")
        return default_result


async def analyze_image_async(client: GeminiClient, image_path: Path) -> dict:
    """
    异步使用 Vision API 分析图片

    Args:
        client: Gemini API 客户端
        image_path: 图片文件路径

    Returns:
        包含语义描述、标签、质量等级等的字典
    """
    default_result = _get_default_result(image_path)

    # 读取图片并编码为 base64
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # 确定 MIME 类型
    ext = image_path.suffix.lower()
    mime_type = MIME_TYPES.get(ext, "image/png")

    # 构建多模态请求
    parts = [
        {"text": VISION_TAGGING_PROMPT},
        {"inlineData": {"mimeType": mime_type, "data": image_data}},
    ]

    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="You are a professional visual content analyst and quality evaluator. Please output in JSON format strictly."
        )
        return _parse_vision_response(response.text, default_result)

    except Exception as e:
        print(f"[Vision Processor] Analysis failed: {e}")
        return default_result
