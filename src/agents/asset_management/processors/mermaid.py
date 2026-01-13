"""
Mermaid Processor

Handles Mermaid diagram generation and extraction.
"""

import re
from typing import Optional

from ....core.gemini_client import GeminiClient


MERMAID_GENERATION_PROMPT = """你是一个 Mermaid 图表专家。请根据以下描述生成一个 Mermaid 图表。

## 描述
{description}

## 风格要求
- 结构清晰，层次分明
- 使用恰当的图表类型（flowchart, sequence, class, state 等）
- 标签简洁明了

{style_hints}

## 输出格式
请直接输出 Mermaid 代码，不要包含任何解释文字。

```mermaid
...
```
"""


def extract_mermaid(text: str) -> Optional[str]:
    """从文本中提取 Mermaid 代码"""
    match = re.search(r'```mermaid\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    return None


async def generate_mermaid_async(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """
    异步生成 Mermaid 图表

    Args:
        client: Gemini API 客户端
        description: 图表描述
        style_hints: 额外的风格提示

    Returns:
        Mermaid 代码或 None
    """
    hints_section = f"## 额外要求\n{style_hints}" if style_hints else ""
    prompt = MERMAID_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="你是一个 Mermaid 图表专家。请生成结构清晰的图表代码。",
            temperature=0.5
        )

        if not response.success:
            print(f"[Mermaid Processor] API 错误: {response.error}")
            return None

        return extract_mermaid(response.text)

    except Exception as e:
        print(f"[Mermaid Processor] 生成失败: {e}")
        return None


def generate_mermaid(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """同步生成 Mermaid 图表"""
    hints_section = f"## 额外要求\n{style_hints}" if style_hints else ""
    prompt = MERMAID_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = client.generate(
            prompt,
            system_instruction="你是一个 Mermaid 图表专家。请生成结构清晰的图表代码。"
        )
        return extract_mermaid(response.text)

    except Exception as e:
        print(f"[Mermaid Processor] 生成失败: {e}")
        return None
