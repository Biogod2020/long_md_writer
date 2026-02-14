"""
SVG Processor

Handles SVG generation and extraction.
"""

import re
from typing import Optional

from ...core.gemini_client import GeminiClient
from ...core.types import AgentState

SVG_GENERATION_PROMPT = """You are a Senior Information Architect and Technical Illustrator. Your goal is to create State-of-the-Art (SOTA) vector graphics that translate complex concepts into intuitive visual metaphors.

## 🎯 YOUR TASK
Create a professional SVG illustration based on the following specific requirements and chapter context:

{description}

{style_hints}

## 🎨 DESIGN PHILOSOPHY (The SOTA Standard)
1. **Visual Hierarchy**: Use line weight, color saturation, and scale to guide the reader's eye. The most critical information must be immediately prominent.
2. **Cognitive Load Management**: Avoid clutter. Use negative space (whitespace) as a functional element to separate concepts.
3. **Professional Finish**: Aim for a modern, precise, and high-quality aesthetic (e.g., subtle gradients, rounded geometric shapes, balanced composition).
4. **Contextual Awareness**: Ensure the diagram feels like an organic part of the overall document.

## 🛠️ TECHNICAL EXECUTION
- Generate strictly valid, self-contained SVG code.
- Use `viewBox` for fluid responsiveness. Set `width="100%"` and `height="auto"`.
- **Avoid Overlapping**: Prevent labels or lines from crossing each other messily.
- **Labeling Strategy**: Place labels where they are most readable. Use leader lines (arrows/paths) to pull text away from high-density areas if needed. 
- **Font Support**: Use system-standard font stacks.

Your output should not just be a 'drawing', but a high-fidelity 'Knowledge Interface'.
"""

SVG_CAPTION_REFINEMENT_PROMPT = """You are a Senior Technical Editor. Your task is to write a precise, factual, and professional caption for the provided SVG illustration.

### Instructions:
1. **Analyze the Image**: Look at what is ACTUALLY rendered in the image (labels, arrows, colors, structures).
2. **Consult Context**: Read the [ARTICLE CONTEXT] to understand the intended narrative and terminology.
3. **Synthesize**: Write a caption that:
   - Describes the core mechanism or concept shown.
   - Specifically mentions key labels visible in the diagram to anchor the text to the visual.
   - Is concise (1-2 sentences) but high-value.
   - Avoids "Here is a diagram showing..." or "This image illustrates...". Start directly with the factual description.
   - Match the language of the [ARTICLE CONTEXT].

### Input Data:
- **Original Directive**: {original_directive}
- **Article Context**: {article_context}

### Final Caption Output:
(Output only the caption text, no JSON or quotes)
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
            temperature=0.5,
            stream=True
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

SVG_REPAIR_PROMPT = """You are a senior SVG technical specialist. Your task is to generate precise JSON patches to fix visual, technical, or logical issues in an SVG file based on audit feedback and article context.

### Input Data:
1. **Original Intent & Context**: {original_intent}
2. **Audit Feedback**: 
   - Issues: {issues}
   - Suggestions: {suggestions}
3. **Current SVG Code**: (See below)
4. **Previous Attempt Feedback**: {feedback}

### Instructions:
- **Logical Alignment**: First, verify if the current SVG's content actually matches the [ARTICLE CONTEXT]. If the diagram is fundamentally representing the wrong subject, prioritize structural changes to match the intended logic.
- **Locate**: Identify the exact lines in the SVG code that need fixing.
- **Transform**: Create a "search" block that matches the existing code EXACTLY and a "replace" block with your fix.
- **Minimal Changes**: Only modify what is necessary.
- **Precision**: Ensure the `search` text is unique enough.
- **Global Awareness**: Ensure adjustments don't trigger new collisions or push elements outside the `viewBox`.
- **Fallback**: If precise patching fails or is too complex, you may provide the COMPLETE repaired SVG code in the `full_code` field.

### Output Format (JSON Only):
{{
  "thought": "Analysis of how this fix aligns the diagram with the specific article context provided.",
  "patches": [
    {{
      "search": "exact text to find",
      "replace": "new text to put in"
    }}
  ],
  "full_code": "Optional: Only use this for complete rewrites if patches are likely to fail."
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
    Repair an SVG by generating targeted patches or full rewrites.
    Implements a 3-attempt escalation loop with rich feedback.
    """
    from ...core.patcher import apply_smart_patch
    from ...core.json_utils import parse_json_dict_robust
    
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "- None"
    suggestions_text = "\n".join(f"- {s}" for s in suggestions) if suggestions else "- None"
    
    current_svg_code = failed_svg_code
    last_feedback = "This is the first repair attempt."

    for attempt in range(max_retries + 1):
        # Prepare the prompt with current code and feedback
        prompt = SVG_REPAIR_PROMPT.format(
            original_intent=original_intent,
            failed_svg_code=current_svg_code,
            issues=issues_text,
            suggestions=suggestions_text,
            feedback=last_feedback
        )
        
        # Multi-modal parts (study the image in every retry)
        parts = []
        if rendered_image_b64:
            parts.append({"text": "## Visual Reference\nStudy this current rendering to locate issues:"})
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": rendered_image_b64}})
        
        parts.append({"text": prompt})

        try:
            print(f"    [SVG Repair] 🛠️ Attempt {attempt + 1}/{max_retries + 1}...")
            response = await client.generate_async(
                parts=parts,
                system_instruction="You are a SOTA SVG Patching Agent. Fix issues using JSON patches or full_code fallback. Output JSON only.",
                temperature=0.0,
                stream=True
            )

            if not response.success:
                last_feedback = f"API Error: {response.error}"
                continue

            if state and response.thoughts:
                state.thoughts += f"\n[SVG Repair Attempt {attempt+1}] {response.thoughts}"

            result = response.json_data if response.json_data else parse_json_dict_robust(response.text)
            if not result:
                last_feedback = "Failed to parse your previous JSON response. Ensure strict JSON format."
                continue

            # 1. Check for Full Code Fallback (Highest Reliability)
            if "full_code" in result and result["full_code"] and len(result["full_code"]) > 50:
                new_code = extract_svg(result["full_code"])
                if new_code:
                    print(f"    [SVG Repair] ✅ Success via Full Rewrite (Attempt {attempt+1})")
                    return new_code

            # 2. Sequential Patching
            if "patches" in result and result["patches"]:
                applied_content = current_svg_code
                patch_errors = []
                
                for i, patch in enumerate(result["patches"]):
                    search = patch.get("search")
                    replace = patch.get("replace")
                    if not search: continue
                    
                    new_content, success = apply_smart_patch(applied_content, search, replace)
                    if success:
                        applied_content = new_content
                    else:
                        patch_errors.append(f"Patch {i+1} FAILED: {new_content}")
                
                if not patch_errors:
                    print(f"    [SVG Repair] ✅ Success via Precision Patching (Attempt {attempt+1})")
                    return applied_content
                else:
                    # Provide specific matching errors back to the AI
                    error_report = "\n".join(patch_errors)
                    last_feedback = f"PATCHING FAILED on attempt {attempt+1}:\n{error_report}\n\nPlease try again with more precise 'search' strings or use the 'full_code' fallback."
                    print(f"    [SVG Repair] ⚠️ Patch matching failed, retrying with feedback...")
            else:
                last_feedback = "No patches or full_code were found in your response. Please provide a fix."

        except Exception as e:
            print(f"    [SVG Repair] Exception: {e}")
            last_feedback = f"System Exception: {str(e)}"
            
    return None


async def refine_svg_caption_async(
    client: GeminiClient,
    original_directive: str,
    article_context: str,
    rendered_image_b64: str,
    state: Optional[AgentState] = None
) -> str:
    """
    Refine the SVG description (caption) based on the actual rendered image.
    Ensures high alignment between text and visual evidence.
    """
    prompt = SVG_CAPTION_REFINEMENT_PROMPT.format(
        original_directive=original_directive,
        article_context=article_context
    )
    
    parts = [
        {"text": "Analyze this final rendered SVG illustration:"},
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": rendered_image_b64
            }
        },
        {"text": prompt}
    ]
    
    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="You are a Technical Copywriter. Write factual captions based on visual evidence.",
            temperature=0.0
        )
        
        if response.success:
            return response.text.strip()
        return original_directive # Fallback to original
    except Exception as e:
        print(f"    [SVGAgent] Caption refinement failed: {e}")
        return original_directive
