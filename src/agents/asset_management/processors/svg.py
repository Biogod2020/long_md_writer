"""
SVG Processor

Handles SVG generation and extraction.
"""

import re
from typing import Optional
from pathlib import Path

from ....core.gemini_client import GeminiClient


SVG_GENERATION_PROMPT = """你是一个专业的 SVG 矢量图形设计师。请根据以下描述生成一个教育性质的 SVG 图形。

## 描述
{description}

## 风格要求
- 简洁清晰，适合教学用途
- 使用柔和的配色方案
- 包含必要的标注和文字说明
- 图形大小建议: 800x600 或适合内容的尺寸

{style_hints}

## 输出格式
请直接输出完整的 SVG 代码，不要包含任何解释文字。SVG 必须是有效的 XML 格式。

```svg
<svg xmlns="http://www.w3.org/2000/svg" ...>
  ...
</svg>
```
"""


def extract_svg(text: str) -> Optional[str]:
    """从文本中提取 SVG 代码"""
    # 尝试匹配 ```svg ... ``` 块
    match = re.search(r'```svg\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()

    # 尝试直接匹配 <svg ...> ... </svg>
    match = re.search(r'<svg[^>]*>[\s\S]*?</svg>', text, re.IGNORECASE)
    if match:
        return match.group(0)

    return None


async def generate_svg_async(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """
    异步生成 SVG 图形

    Args:
        client: Gemini API 客户端
        description: 图形描述
        style_hints: 额外的风格提示

    Returns:
        SVG 代码或 None
    """
    hints_section = f"## 额外风格要求\n{style_hints}" if style_hints else ""
    prompt = SVG_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="你是一个专业的 SVG 矢量图形设计师。请生成清晰、教育性强的 SVG 图形。",
            temperature=0.5
        )

        if not response.success:
            print(f"[SVG Processor] API 错误: {response.error}")
            return None

        return extract_svg(response.text)

    except Exception as e:
        print(f"[SVG Processor] 生成失败: {e}")
        return None


def generate_svg(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """同步生成 SVG 图形"""
    hints_section = f"## 额外风格要求\n{style_hints}" if style_hints else ""
    prompt = SVG_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = client.generate(
            prompt,
            system_instruction="你是一个专业的 SVG 矢量图形设计师。请生成清晰、教育性强的 SVG 图形。"
        )
        return extract_svg(response.text)

    except Exception as e:
        print(f"[SVG Processor] 生成失败: {e}")
        return None
