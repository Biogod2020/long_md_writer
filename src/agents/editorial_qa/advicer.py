"""
Editorial Advicer Component (SOTA 2.0 Phase E)
Translates global critiques into granular patching instructions for the merged file.
"""

import json
from typing import Dict
from ...core.gemini_client import GeminiClient
from ...core.json_utils import parse_json_dict_robust
from .prompts import EDITORIAL_ADVICER_SYSTEM_PROMPT

async def run_editorial_advicer(
    client: GeminiClient,
    merged_content: str,
    critic_feedback: str,
    debug: bool = False
) -> Dict[str, str]:
    """Generates specific editing instructions for final_full.md."""
    
    prompt = f"""# Critic's Global Feedback
{critic_feedback}

# Full Merged Content (final_full.md)
{merged_content}

---
Provide specific, actionable instructions for final_full.md to resolve the identified errors.
Return ONLY valid JSON.
"""
    
    response = await client.generate_async(
        prompt=prompt,
        system_instruction=EDITORIAL_ADVICER_SYSTEM_PROMPT,
        temperature=0.0,
        stream=True
    )
    
    if not response.success:
        print(f"    [EditorialAdvicer] ❌ API Failed: {response.error}")
        return {}
        
    return parse_json_dict_robust(response.text)
