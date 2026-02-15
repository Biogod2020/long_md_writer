"""
Editorial Critic Component (SOTA 2.0 Phase E)
Evaluates the MERGED full document for global consistency and structural rigor.
Supports Multimodal input (screenshots) for visual alignment.
"""

import json
import base64
import io
from pathlib import Path
from typing import Optional, Dict, List
from PIL import Image

from ...core.gemini_client import GeminiClient
from ...core.types import AgentState
from ...core.json_utils import parse_json_dict_robust
from .prompts import EDITORIAL_CRITIC_SYSTEM_PROMPT

async def run_editorial_critic(
    client: GeminiClient,
    state: AgentState,
    merged_content: str,
    screenshot_paths: Optional[List[Path]] = None,
    debug: bool = False
) -> Dict:
    """Executes a full-context global audit on the merged content."""
    
    # 1. Prepare context info
    manifest_info = {
        "project_title": state.manifest.project_title,
        "description": state.manifest.description,
        "sections": [
            {"id": s.id, "title": s.title, "summary": s.summary} 
            for s in state.manifest.sections
        ]
    }

    text_prompt = f"""# Project Brief
{state.project_brief}

# Approved Manifest
{json.dumps(manifest_info, indent=2, ensure_ascii=False)}

# Merged Full Document (final_full.md)
```markdown
{merged_content}
```

---
Perform a macro-level audit on the merged document above. 
Focus on global hierarchy, terminology consistency, and narrative flow.
"""
    
    parts = [{"text": text_prompt}]
    
    # 2. Multimodal Injection (Visual Evidence)
    if screenshot_paths:
        for i, path in enumerate(screenshot_paths):
            try:
                with Image.open(path) as img:
                    if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
                    if img.width > 1200:
                        ratio = 1200 / img.width
                        img = img.resize((1200, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=80)
                    image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    
                    parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})
                    parts.append({"text": f"[Visual Evidence: Screenshot Part {i+1}]"})
            except Exception as e:
                print(f"    [EditorialCritic] Error loading image {path}: {e}")

    parts.append({"text": "\nOutput ONLY valid JSON."})

    response = await client.generate_async(
        parts=parts,
        system_instruction=EDITORIAL_CRITIC_SYSTEM_PROMPT,
        temperature=0.0,
        stream=True
    )
    
    if not response.success:
        print(f"    [EditorialCritic] ❌ API Failed: {response.error}")
        return {"verdict": "MODIFY", "feedback": f"API Error: {response.error}"}

    result = parse_json_dict_robust(response.text)
    if result:
        result["verdict"] = result.get("verdict", "MODIFY").upper()
        return result
    else:
        # Salvage log
        log_file = Path(state.workspace_path) / "debug_failed_editorial_critic.txt"
        log_file.write_text(response.text, encoding="utf-8")
        return {"verdict": "MODIFY", "feedback": "JSON Parse Error in Critic response."}
