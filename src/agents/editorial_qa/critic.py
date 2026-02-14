"""
Editorial Critic Component (SOTA 2.0 Phase E)
Evaluates the MERGED full document for global consistency and structural rigor.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List
from ...core.gemini_client import GeminiClient
from ...core.types import AgentState
from ...core.json_utils import parse_json_dict_robust
from .prompts import EDITORIAL_CRITIC_SYSTEM_PROMPT

async def run_editorial_critic(
    client: GeminiClient,
    state: AgentState,
    merged_content: str,
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

    prompt = f"""# Project Brief
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
Output ONLY valid JSON.
"""

    if debug:
        print(f"    [EditorialCritic] Prompt size: {len(prompt)} chars")

    response = await client.generate_async(
        prompt=prompt,
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
