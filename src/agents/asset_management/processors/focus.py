"""
Focus Processor

Handles VLM-based focus calculation for images.
"""

import re
import json
import base64
from pathlib import Path
from typing import Optional

from ....core.gemini_client import GeminiClient
from ....core.types import CropMetadata


FOCUS_CALCULATION_PROMPT = """分析这张图片，找到以下描述对应的视觉焦点位置：

焦点描述: {focus_description}

请返回焦点的百分比坐标，格式如下：
```json
{{
  "left": "50%",
  "top": "50%",
  "zoom": 1.0,
  "reasoning": "简短解释为什么选择这个位置"
}}
```

注意：
- left 是水平位置，0% 表示最左边，100% 表示最右边
- top 是垂直位置，0% 表示最上边，100% 表示最下边
- zoom 是缩放因子，1.0 表示不缩放，>1 表示放大
"""


# MIME 类型映射
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def compute_focus(
    client: GeminiClient,
    image_path: Path,
    focus_description: str
) -> Optional[CropMetadata]:
    """
    使用 VLM 计算图片的焦点位置

    Args:
        client: Gemini API 客户端
        image_path: 图片文件路径
        focus_description: 焦点描述

    Returns:
        CropMetadata 或 None
    """
    if not image_path.exists():
        return None

    # 读取图片
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # 确定 MIME 类型
    ext = image_path.suffix.lower()
    mime_type = MIME_TYPES.get(ext, "image/png")

    # 构建多模态请求
    prompt = FOCUS_CALCULATION_PROMPT.format(focus_description=focus_description)
    parts = [
        {"text": prompt},
        {"inlineData": {"mimeType": mime_type, "data": image_data}},
    ]

    try:
        response = client.generate(
            parts=parts,
            system_instruction="你是一个视觉分析专家。请精确定位图片中的焦点区域。"
        )

        # 解析 JSON 响应
        json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return CropMetadata(
                left=data.get("left", "50%"),
                top=data.get("top", "50%"),
                zoom=float(data.get("zoom", 1.0)),
            )

    except Exception as e:
        print(f"[Focus Processor] 焦点计算失败: {e}")

    return None


async def compute_focus_async(
    client: GeminiClient,
    image_path: Path,
    focus_description: str
) -> Optional[CropMetadata]:
    """
    异步使用 VLM 计算图片的焦点位置

    Args:
        client: Gemini API 客户端
        image_path: 图片文件路径
        focus_description: 焦点描述

    Returns:
        CropMetadata 或 None
    """
    if not image_path.exists():
        return None

    # 读取图片
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # 确定 MIME 类型
    ext = image_path.suffix.lower()
    mime_type = MIME_TYPES.get(ext, "image/png")

    # 构建多模态请求
    prompt = FOCUS_CALCULATION_PROMPT.format(focus_description=focus_description)
    parts = [
        {"text": prompt},
        {"inlineData": {"mimeType": mime_type, "data": image_data}},
    ]

    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="你是一个视觉分析专家。请精确定位图片中的焦点区域。"
        )

        if not response.success:
            return None

        # 解析 JSON 响应
        json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return CropMetadata(
                left=data.get("left", "50%"),
                top=data.get("top", "50%"),
                zoom=float(data.get("zoom", 1.0)),
            )

    except Exception as e:
        print(f"[Focus Processor] 焦点计算失败: {e}")

    return None
