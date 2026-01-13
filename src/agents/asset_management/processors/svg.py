"""
SVG Processor

Handles SVG generation and extraction.
"""

import re
import asyncio
from typing import Optional
from pathlib import Path

from ....core.gemini_client import GeminiClient


SVG_GENERATION_PROMPT = """You are a professional SVG designer and illustrator. Create high-quality vector graphics that are clear, accurate, and aesthetically pleasing.

## Content Description
{description}

## Design Principles
1. **Legibility & Clarity**: Ensure all text and elements are easily readable. Use adequate contrast and prevent overlaps between text and paths.
2. **Visual Balance**: Maintain a balanced composition with consistent alignment and professional spacing.
3. **Detail & Hierarchy**: Use appropriate line weights and color gradients to establish a clear visual hierarchy.
4. **Professional Aesthetics**: Aim for a modern, clean look. Avoid overly simplistic or "childish" shapes unless specified.

{style_hints}

## Technical Requirements
- Output ONLY valid SVG code.
- Ensure the SVG is responsive (use viewBox).
- Avoid external assets or fonts; use standard web-safe fonts if text is needed.
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
    """异步生成 SVG 图形"""
    hints_section = f"## Additional Style\n{style_hints}" if style_hints else ""
    prompt = SVG_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="You are a professional SVG designer. Create accurate, readable, and aesthetically pleasing vector graphics.",
            temperature=0.5
        )

        if not response.success:
            print(f"[SVG Processor] API error: {response.error}")
            return None

        return extract_svg(response.text)

    except Exception as e:
        print(f"[SVG Processor] Generation failed: {e}")
        return None


def generate_svg(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """同步生成 SVG 图形"""
    hints_section = f"## Additional Style\n{style_hints}" if style_hints else ""
    prompt = SVG_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = client.generate(
            prompt,
            system_instruction="You are a professional SVG designer. Create accurate, readable, and aesthetically pleasing vector graphics."
        )
        return extract_svg(response.text)

    except Exception as e:
        print(f"[SVG Processor] Generation failed: {e}")
        return None


# ============================================================================
# SVG Repair (Full Regeneration with Visual Context)
# ============================================================================

SVG_REPAIR_PROMPT = """You are a senior SVG specialist. Your task is to fix and improve the provided SVG based on specific audit feedback.

## Original Intent
{original_intent}

## Refinement Goals
- **Correctness**: Resolve all scientific, technical, or logical errors.
- **Visual Refinement**: Improve clarity, fix alignment/overlaps, and enhance overall professional appearance.
- **Consistency**: Ensure the design remains cohesive and follows standard best practices.

## Audit Feedback
### Issues:
{issues}

### Suggestions:
{suggestions}

## Current SVG Code (Reference)
{failed_svg_code}

## Task
Output the COMPLETE and fixed SVG code. Apply both the functional fixes and aesthetic polish mentioned in the feedback. 
Return ONLY valid SVG code, no conversational filler or markdown explanations.
"""


async def repair_svg_async(
    client: GeminiClient,
    original_intent: str,
    failed_svg_code: str,
    issues: list[str],
    suggestions: list[str],
    rendered_image_b64: Optional[str] = None,
    max_retries: int = 2
) -> Optional[str]:
    """
    Repair an SVG by generating a complete fixed version.
    
    If rendered_image_b64 is provided, the model can "see" the visual issues
    and make more accurate fixes.
    """
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "- None specified"
    suggestions_text = "\n".join(f"- {s}" for s in suggestions) if suggestions else "- None specified"
    
    prompt = SVG_REPAIR_PROMPT.format(
        original_intent=original_intent,
        failed_svg_code=failed_svg_code[:8000],  # Limit to avoid token overflow
        issues=issues_text,
        suggestions=suggestions_text
    )
    
    # Build multi-modal parts if image is provided
    if rendered_image_b64:
        parts = [
            {"text": "## Current Rendered Image (What needs fixing)\nLook at this image to understand the visual problems:"},
            {"inlineData": {"mimeType": "image/png", "data": rendered_image_b64}},
            {"text": prompt}
        ]
    else:
        parts = None

    for attempt in range(max_retries + 1):
        try:
            if parts:
                response = await client.generate_async(
                    parts=parts,
                    system_instruction="You are a senior SVG illustrator. Elevate the aesthetics and fix all errors. Output a complete fixed SVG.",
                    temperature=0.2
                )
            else:
                response = await client.generate_async(
                    prompt=prompt,
                    system_instruction="You are a senior SVG illustrator. Output a complete fixed SVG with textbook-grade aesthetics.",
                    temperature=0.2
                )

            if not response.success:
                if attempt < max_retries:
                    print(f"[SVG Repair] Retry {attempt + 1}/{max_retries}...")
                    await asyncio.sleep(1)
                    continue
                return None

            result = extract_svg(response.text)
            if result:
                return result
            
            if attempt < max_retries:
                print(f"[SVG Repair] No valid SVG in response, retrying...")
                continue
            return None

        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            print(f"[SVG Repair] Repair failed: {e}")
            return None
    
    return None
