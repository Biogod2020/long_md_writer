"""
SVG Processor

Handles SVG generation and extraction.
"""

import re
import asyncio
from typing import Optional
from pathlib import Path

from ....core.gemini_client import GeminiClient
from ....core.types import AgentState

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
- Avoid external assets or fonts.
- **CRITICAL: Font Support**: For all text elements, use `font-family="system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'"` to ensure CJK (Chinese/Japanese/Korean) characters render correctly across different operating systems.
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
    state: Optional[AgentState] = None,
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

        # Capture thoughts
        if state and response.thoughts:
            state.thoughts += f"\n[SVG Generation] {response.thoughts}"

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
            prompt=prompt,
            system_instruction="You are a professional SVG designer. Create accurate, readable, and aesthetically pleasing vector graphics."
        )
        return extract_svg(response.text)

    except Exception as e:
        print(f"[SVG Processor] Generation failed: {e}")
        return None


# ============================================================================
# SVG Repair (High-Precision Patching with Visual Context)
# ============================================================================

SVG_REPAIR_PROMPT = """You are a senior SVG technical specialist. Your task is to generate precise JSON patches to fix visual or technical issues in an SVG file based on audit feedback.

### Input Data:
1. **Original Intent**: {original_intent}
2. **Audit Feedback**: 
   - Issues: {issues}
   - Suggestions: {suggestions}
3. **Current SVG Code**: (See below)

### Instructions:
- **Locate**: Identify the exact lines in the SVG code that need fixing (e.g., overlapping coordinates, missing attributes, incorrect colors).
- **Transform**: Create a "search" block that matches the existing code EXACTLY and a "replace" block with your fix.
- **Minimal Changes**: Only modify what is broken. Do not rewrite the entire file.
- **Precision**: Ensure the `search` text is unique enough to find the correct spot.

### Output Format (JSON Only):
{{
  "thought": "Analysis of why these specific coordinates/attributes need to be changed.",
  "patches": [
    {{
      "search": "exact text to find",
      "replace": "new text to put in"
    }}
  ]
}}

## CURRENT SVG CODE (Immutable Source)
```svg
{failed_svg_code}
```
"""

async def repair_svg_async(
    client: GeminiClient,
    original_intent: str,
    failed_svg_code: str,
    issues: list[str],
    suggestions: list[str],
    state: Optional[AgentState] = None,
    rendered_image_b64: Optional[str] = None,
    max_retries: int = 2
) -> Optional[str]:
    """
    Repair an SVG by generating targeted patches instead of full regeneration.
    Uses the Universal High-Precision Patcher to apply fixes.
    """
    from ....core.patcher import apply_smart_patch
    from ....core.json_utils import parse_json_dict_robust
    
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "- None"
    suggestions_text = "\n".join(f"- {s}" for s in suggestions) if suggestions else "- None"
    
    # We include full code in the prompt as requested
    prompt = SVG_REPAIR_PROMPT.format(
        original_intent=original_intent,
        failed_svg_code=failed_svg_code,
        issues=issues_text,
        suggestions=suggestions_text
    )
    
    # Multi-modal parts
    parts = []
    if rendered_image_b64:
        parts.append({"text": "## Visual Reference of Errors\nStudy this screenshot to identify where elements are overlapping or incorrect:"})
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg", 
                "data": rendered_image_b64
            }
        })
    
    parts.append({"text": prompt})

    for attempt in range(max_retries + 1):
        try:
            response = await client.generate_async(
                parts=parts,
                system_instruction="You are a SOTA SVG Patching Agent. Fix specific visual bugs using JSON patches. Output JSON only.",
                temperature=0.0, # Zero temp for precision patching
                stream=True
            )

            if not response.success:
                if attempt < max_retries: continue
                return None

            # Capture thoughts
            if state and response.thoughts:
                state.thoughts += f"\n[SVG Patch Repair Attempt {attempt+1}] {response.thoughts}"

            # Parse patches
            result = response.json_data if response.json_data else parse_json_dict_robust(response.text)
            if not result or "patches" not in result:
                continue

            # Apply patches sequentially
            current_content = failed_svg_code
            applied_any = False
            for patch in result.get("patches", []):
                search_text = patch.get("search")
                replace_text = patch.get("replace")
                if search_text:
                    new_content, success = apply_smart_patch(current_content, search_text, replace_text)
                    if success:
                        current_content = new_content
                        applied_any = True
                    else:
                        print(f"    [SVG Repair] ⚠️ Patch failed to match: {search_text[:50]}...")
            
            if applied_any:
                return current_content
            
            if attempt < max_retries:
                print(f"    [SVG Repair] No patches applied successfully, retrying...")
                continue
            
        except Exception as e:
            print(f"    [SVG Repair] Exception during repair: {e}")
            if attempt < max_retries: continue
            
    return None
