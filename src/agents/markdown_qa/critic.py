"""
Critic Component for Markdown QA
Evaluates Markdown content against the Manifest, Project Brief, and Raw Materials.
Uses un-cut context and streaming for robustness.
"""

import json
from pathlib import Path
from typing import Dict, Optional, List
from src.core.gemini_client import GeminiClient
from src.core.json_utils import parse_json_dict_robust

CRITIC_SYSTEM_PROMPT = """You are a Ruthless Scientific Editor and Lead QA Engineer. 
Your goal is to perform a rigorous audit of the generated Markdown content against the provided Project Manifest and Project Brief.

### Evaluation Protocol:
1. **Manifest Alignment (CRITICAL)**: 
   - Open the Project Manifest. 
   - For EACH section, check if the actual content covers the "summary" and "knowledge_map" points.
   - If a specific mathematical derivation or concept is mentioned in the Manifest summary but is MISSING or too thin in the text, you MUST give a "MODIFY" or "REWRITE" verdict.
2. **Technical Rigor**:
   - Verify all MathJax equations. Are they present where requested?
   - Is the "Technical Vibe" from the Manifest being maintained?
3. **Logic & Narrative**:
   - Does each section transition naturally to the next?
   - Is the language consistent with the Project Brief?
4. **Formatting**:
   - Check for broken Mermaid/SVG blocks, duplicate titles, or improper heading levels.

### Verdicts:
- **APPROVE**: Perfect alignment. All technical derivations from the Manifest are present and accurate.
- **MODIFY**: Content is good but misses specific technical points, has typos, or formatting issues. Use this for "missing a specific derivation".
- **REWRITE**: Use if the document fails on a fundamental level (wrong language, missing entire chapters, or hallucinating content that isn't in the provided text).

### Output Format (JSON):
{
  "verdict": "APPROVE" | "MODIFY" | "REWRITE",
  "feedback": "Explain EXACTLY what is missing or incorrect, referencing specific Manifest requirements.",
  "section_feedback": {
      "filename.md": "Missing KCL derivation as required by Manifest Section ID 'phase-01'.",
      "..."
  }
}

NOTE: Do NOT hallucinate content. If you state 'The math is accurate', ensured you actually SEE the math in the 'Merged Markdown Content'. If the math is missing, be blunt.
"""

async def run_markdown_critic(
    client: GeminiClient,
    state, # AgentState
    merged_content: str,
    debug: bool = False
) -> Dict:
    """
    Run the Critic to evaluate content.
    """
    # 1. Prepare Manifest & Context (SOTA: Include summaries for better quality check)
    manifest_info = {
        "project_title": state.manifest.project_title,
        "sections": [
            {
                "id": s.id, 
                "title": s.title, 
                "summary": s.summary,
                "metadata": s.metadata
            } for s in state.manifest.sections
        ]
    }
    
    file_list = [Path(p).name for p in state.completed_md_sections]

    prompt = f"""# Manifest
{json.dumps(manifest_info, indent=2, ensure_ascii=False)}

# Project Brief
{state.project_brief}

# Raw Materials
{state.raw_materials}

# Available Files
{json.dumps(file_list, indent=2)}

# Merged Markdown Content
{merged_content}

---
Evaluate the content above. 
If the content is in the wrong language (e.g., English instead of Chinese), verdict MUST be "REWRITE".
If the content has factual errors or minor style issues, verdict "MODIFY".
If perfect, "APPROVE".
"""

    if debug:
        print(f"    [Critic] Prompt size: {len(prompt)} chars")

    # 2. Call API with Streaming enabled (Reverted to stream=True as requested)
    response = await client.generate_async(
        prompt=prompt,
        system_instruction=CRITIC_SYSTEM_PROMPT,
        temperature=0.0,
        stream=True
    )
    
    if not response.success:
        print(f"    [Critic] ❌ API Failed: {response.error}")
        return {"verdict": "REWRITE", "feedback": f"API Error, please retry. Details: {response.error}"}

    text = response.text.strip()
    
    # 3. Parse JSON using robust utility
    result = parse_json_dict_robust(text)
    if result:
        # Normalize verdict keys
        if "verdict" in result:
            result["verdict"] = result["verdict"].upper()
        return result
    else:
        print(f"    [Critic] ⚠️ JSON Parse Error from robust parser.")
        # Fallback based on keywords
        verdict = "MODIFY"
        if "rewrite" in text.lower():
            verdict = "REWRITE"
        elif "approve" in text.lower() or "pass" in text.lower():
            verdict = "APPROVE"
            
        return {"verdict": verdict, "feedback": text}
