import re
import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from ....core.gemini_client import GeminiClient
from ....core.types import AgentState


MERMAID_GENERATION_PROMPT = """You are a Mermaid.js diagram expert. Create a clear, well-structured, and aesthetically pleasing diagram based on the provided description.

## Content Description
{description}

## Design Principles
- **Clarity & Structure**: Organize the diagram logically with clear hierarchies and connections.
- **Appropriate Chart Type**: Choose the most suitable Mermaid chart type for the data.
- **Concise Labels**: Use brief and descriptive text.
- **Visual Polish**: Use subgraphs, styling classes, or direction (TB, LR) where appropriate.

{style_hints}

## Output Format
Return ONLY the Mermaid code block.

```mermaid
...
```
"""

MERMAID_AUDIT_PROMPT = """You are a technical auditor for Mermaid.js diagrams. Evaluate the provided diagram against technical requirements and visual clarity.

## Intent Description
{intent_description}

## Mermaid Code
```mermaid
{mermaid_code}
```

## Scoring Rubric (0-100)
1. **Accuracy (40%)**: Does it represent the described logic/data correctly?
2. **Syntax & Completeness (30%)**: Is it valid Mermaid syntax?
3. **Visual Clarity (30%)**: Is the layout easy to read?

## Output (JSON only)
```json
{{
  "accuracy_score": 0,
  "syntax_score": 0,
  "clarity_score": 0,
  "overall_score": 0,
  "result": "pass|fail|needs_revision",
  "issues": [],
  "suggestions": []
}}
```
"""

MERMAID_REPAIR_PROMPT = """You are a senior Mermaid.js specialist. Your task is to generate precise JSON patches to fix issues in a Mermaid diagram based on audit feedback.

### Input Data:
1. **Original Intent**: {original_intent}
2. **Audit Feedback**: {issues}
3. **Current Mermaid Code**: (See below)

### Instructions:
- **Locate**: Identify specific lines in the Mermaid code that need fixing.
- **Transform**: Create a "search" block that matches the existing code EXACTLY and a "replace" block with your fix.
- **Minimal Changes**: Only modify what is broken to preserve the rest of the diagram.

### Output Format (JSON Only):
{{
  "thought": "Analysis of why these specific diagram components need adjustment.",
  "patches": [
    {{
      "search": "exact line or block to find",
      "replace": "new line or block to put in"
    }}
  ]
}}

## CURRENT MERMAID CODE
```mermaid
{failed_code}
```
"""


def extract_mermaid(text: str) -> Optional[str]:
    """Extract Mermaid code from text"""
    match = re.search(r'```mermaid\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    if "graph " in text or "sequenceDiagram" in text or "classDiagram" in text:
        return text.strip()
    return None


async def render_mermaid_to_png(mermaid_code: str, output_path: Path) -> bool:
    """
    SOTA Mermaid Renderer for VLM Auditing.
    Uses high-resolution Headless Chromium to capture crystal-clear snapshots.
    """
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>
            mermaid.initialize({{ 
                startOnLoad: true, 
                theme: 'default',
                fontFamily: 'Inter, system-ui, sans-serif',
                fontSize: 16,
                flowchart: {{ useMaxWidth: false, htmlLabels: true }},
                sequence: {{ useMaxWidth: false, showSequenceNumbers: true }}
            }});
        </script>
        <style>
            html, body {{ margin: 0; padding: 0; background: white; }}
            body {{ display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; padding: 40px; }}
            .mermaid {{ 
                min-width: 600px; 
                display: inline-block;
            }}
            /* Ensure high-contrast for VLM */
            svg {{ filter: contrast(1.1) brightness(1.05); }}
        </style>
    </head>
    <body>
        <div class="mermaid">
            {mermaid_code}
        </div>
    </body>
    </html>
    """
    
    temp_html = output_path.with_suffix(".html")
    temp_html.write_text(html_template, encoding="utf-8")
    
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            # SOTA: 使用高分辨率 Viewport 和设备缩放
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1280},
                device_scale_factor=2 # 2x 缩放确保文字极其清晰
            )
            page = await context.new_page()
            await page.goto(f"file://{temp_html.absolute()}", wait_until="networkidle")
            
            try:
                # 智能等待 Mermaid 渲染完成
                await page.wait_for_selector(".mermaid svg", timeout=15000)
                # 给予额外的微小延迟以确保布局抖动结束
                await asyncio.sleep(0.8)
                
                # 仅对 Mermaid 容器截图，保持紧凑
                element = await page.query_selector(".mermaid")
                if element:
                    await element.screenshot(path=str(output_path))
                else:
                    await page.screenshot(path=str(output_path), full_page=True)
                
                # 压缩为高质量 JPEG 以减少 API 负载
                from PIL import Image
                with Image.open(output_path) as img:
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.save(output_path, format="JPEG", quality=90, optimize=True)
                    
                return True
            except Exception as e:
                print(f"[Mermaid Render] ⚠️ Snapshot failed: {e}")
            finally:
                await browser.close()
    except Exception as e:
        print(f"[Mermaid Render] Playwright error: {e}")
    finally:
        if temp_html.exists():
            temp_html.unlink()
            
    return False


async def audit_mermaid_async(
    client: GeminiClient,
    mermaid_code: str,
    intent_description: str,
    state: Optional[AgentState] = None
) -> Optional[Dict[str, Any]]:
    """Audit Mermaid diagram code and visual output."""
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    png_b64 = None
    if await render_mermaid_to_png(mermaid_code, tmp_path):
        try:
            with open(tmp_path, "rb") as f:
                png_b64 = base64.b64encode(f.read()).decode("utf-8")
        finally:
            tmp_path.unlink(missing_ok=True)
            
    prompt = MERMAID_AUDIT_PROMPT.format(
        intent_description=intent_description,
        mermaid_code=mermaid_code
    )
    
    parts = [{"text": prompt}]
    if png_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": png_b64
            }
        })
        parts.append({"text": "## Rendered Visual (for verification)"})

    try:
        response = await client.generate_async(
            parts=parts,
            system_instruction="You are a Mermaid technical auditor. Output JSON only.",
            temperature=0.0,
            stream=True
        )
        
        if not response.success:
            return None
            
        if state and response.thoughts:
            state.thoughts += f"\n[Mermaid Audit] {response.thoughts}"

        from ....core.json_utils import parse_json_dict_robust
        return response.json_data if response.json_data else parse_json_dict_robust(response.text)
    except Exception as e:
        print(f"[Mermaid Audit] Failed: {e}")
        return None


async def repair_mermaid_async(
    client: GeminiClient,
    original_intent: str,
    failed_code: str,
    issues: list[str],
    suggestions: list[str],
    state: Optional[AgentState] = None,
    max_retries: int = 2
) -> Optional[str]:
    """Repair Mermaid code using targeted patches."""
    from ....core.patcher import apply_smart_patch
    from ....core.json_utils import parse_json_dict_robust
    
    feedback = "\n".join([f"- {i}" for i in issues] + [f"- Suggestion: {s}" for s in suggestions])
    
    prompt = MERMAID_REPAIR_PROMPT.format(
        original_intent=original_intent,
        issues=feedback,
        failed_code=failed_code
    )
    
    for attempt in range(max_retries + 1):
        try:
            response = await client.generate_async(
                prompt=prompt,
                system_instruction="You are a SOTA Mermaid Patching Agent. Fix diagrams using JSON patches.",
                temperature=0.0,
                stream=True
            )
            
            if response.success:
                if state and response.thoughts:
                    state.thoughts += f"\n[Mermaid Patch Attempt {attempt+1}] {response.thoughts}"
                
                result = response.json_data if response.json_data else parse_json_dict_robust(response.text)
                if not result or "patches" not in result:
                    continue

                current_content = failed_code
                applied_any = False
                for patch in result.get("patches", []):
                    search_text = patch.get("search")
                    replace_text = patch.get("replace")
                    if search_text:
                        new_content, success = apply_smart_patch(current_content, search_text, replace_text)
                        if success:
                            current_content = new_content
                            applied_any = True
                
                if applied_any:
                    return current_content
            
            if attempt < max_retries:
                await asyncio.sleep(1)
        except Exception as e:
            print(f"[Mermaid Repair] Attempt {attempt} failed: {e}")
            
    return None


async def generate_mermaid_async(
    client: GeminiClient,
    description: str,
    state: Optional[AgentState] = None,
    style_hints: str = ""
) -> Optional[str]:
    """Generate a Mermaid diagram asynchronously."""
    hints_section = f"## Additional Requirements\n{style_hints}" if style_hints else ""
    prompt = MERMAID_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = await client.generate_async(
            prompt=prompt,
            system_instruction="You are a Mermaid.js diagram expert. Generate clear and well-structured diagram code.",
            temperature=0.5,
            stream=True
        )

        if not response.success:
            print(f"[Mermaid Processor] API error: {response.error}")
            return None

        if state and response.thoughts:
            state.thoughts += f"\n[Mermaid Generation] {response.thoughts}"

        return extract_mermaid(response.text)

    except Exception as e:
        print(f"[Mermaid Processor] Generation failed: {e}")
        return None


def generate_mermaid(
    client: GeminiClient,
    description: str,
    style_hints: str = ""
) -> Optional[str]:
    """Generate a Mermaid diagram synchronously."""
    hints_section = f"## Additional Requirements\n{style_hints}" if style_hints else ""
    prompt = MERMAID_GENERATION_PROMPT.format(
        description=description,
        style_hints=hints_section
    )

    try:
        response = client.generate(
            prompt=prompt,
            system_instruction="You are a Mermaid.js diagram expert. Generate clear and well-structured diagram code."
        )
        return extract_mermaid(response.text)

    except Exception as e:
        print(f"[Mermaid Processor] Generation failed: {e}")
        return None