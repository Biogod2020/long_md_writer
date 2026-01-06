"""
Advicer Component for Markdown QA
Translates high-level critique into specific, actionable instructions for each file.
"""

import json
import re
from typing import Dict, List, Optional
from src.core.gemini_client import GeminiClient, GeminiResponse
from src.core.json_utils import parse_json_dict_robust

# Using a generic prompt to get specific advice per file
ADVICER_SYSTEM_PROMPT = """You are a Solution Architect for content revision.
Your task is to translate the Lead Editor's feedback into specific, actionable editing instructions for individual files.

Input:
1. Critic's Feedback (General + Section-specific)
2. Merged Markdown Content
3. File List

Output:
A JSON object mapping EACH filename that needs changes to a specific "advice" string.
Format:
{
  "filename.md": "Specific instruction 1. Specific instruction 2..."
}

Rules:
- THE INSTRUCTIONS MUST BE ACTIONABLE. Don't say "fix the tone", say "change 'you' to 'the user'".
- Look at the 'section_feedback' from the Critic to know what to fix in each file.
- Only include files that actually need changes.
"""

async def run_markdown_advicer(
    client: GeminiClient,
    merged_content: str,
    file_list: List[str],
    critic_feedback: str,
    debug: bool = False
) -> Dict[str, str]:
    """
    Run the Advicer to generate specific instructions per file.
    """
    files_json = json.dumps(file_list, indent=2)
    
    prompt = f"""# Critic's General Feedback
{critic_feedback}

# Available Files
{files_json}

# Merged Content
{merged_content}

---
Based on the feedback above, provide specific editing instructions for relevant files.
Return ONLY valid JSON.
"""
    
    # We use stream=True as requested for generic handling
    response = await client.generate_async(
        prompt=prompt,
        system_instruction=ADVICER_SYSTEM_PROMPT,
        temperature=0.0,
        stream=True
    )
    
    if not response.success:
        print(f"    [Advicer] ❌ API Failed: {response.error}")
        return {}
        
    text = response.text.strip()
    if debug:
        print(f"    [Advicer] Raw Output: {text[:500]}...")
        
    advice_map = parse_json_dict_robust(text)
    if advice_map:
        return advice_map
    else:
        print(f"    [Advicer] ⚠️ JSON Parse Error from robust parser.")
        return {}
