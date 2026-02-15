"""
Critic Component for Markdown QA
Evaluates Markdown content against the Manifest, Project Brief, and Raw Materials.
Uses un-cut context and streaming for robustness.
"""

import json
from pathlib import Path
from typing import Dict
from src.core.gemini_client import GeminiClient
from src.core.json_utils import parse_json_dict_robust

CRITIC_SYSTEM_PROMPT = """You are a Senior Managing Editor and Lead Technical Auditor. Your mission is to ensure the entire document set reaches the SOTA standard of intellectual depth, logical harmony, and visual rigor.

## Audit Philosophy: Full Context, Localized Action
You have access to the complete document history to ensure seamless transitions and consistent terminology. However, you must respect the **Historical Stability** of the project.

### 1. Technical & Visual Rigor
- **Visual Logic Audit**: You MUST scrutinize the `description` inside every `:::visual` directive. Ask: "Is this description precise enough to guide a technical illustrator?" Reject descriptions that are vague, generic, or logically inconsistent with the text.
- **Cross-Domain Accuracy**: Ensure the core mechanisms and concepts are described with pedagogical clarity.
- **Terminology Consistency**: Ensure specialized terms are used consistently across all sections.

### 2. The Stability Guardrail (Finalized History)
Sections 1 through N-1 are considered **Finalized Canonical History**. 
- **DO NOT** suggest modifications to finalized sections for stylistic polish.
- **ONLY** trigger a modification for a finalized section if you identify a **Fatal Logical Contradiction** or a **Critical Technical Error**.

### Verdicts:
- **APPROVE**: Coherent and rigorous. Minor stylistic nitpicks are ignored to protect stability.
- **MODIFY**: Technical gaps exist, or visual descriptions are insufficient/incorrect in the CURRENT section.
- **REWRITE**: Fundamental failures (wrong language, total hallucination, catastrophic logic collapse).

### Output Format (JSON):
```json
{
  "verdict": "APPROVE" | "MODIFY" | "REWRITE",
  "thought": "Strategic reasoning, specifically addressing 'Visual Logic' and 'History Protection'.",
  "feedback": "Actionable executive summary of issues.",
  "section_feedback": {
      "current_filename.md": "Precise, actionable instructions for the current work.",
      "previous_filename.md": "ONLY provide this for Fatal/Critical errors."
  }
}
```
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
    # 1. Prepare Manifest & Context (SOTA: Filter to only include PRESENT sections)
    present_section_ids = [Path(p).stem for p in state.completed_md_sections]
    
    manifest_info = {
        "project_title": state.manifest.project_title,
        "sections": [
            {
                "id": s.id, 
                "title": s.title, 
                "summary": s.summary,
                "metadata": s.metadata
            } for s in state.manifest.sections if s.id in present_section_ids
        ]
    }
    
    file_list = [Path(p).name for p in state.completed_md_sections]

    # SOTA: Inject feedback from rejected patches if any
    rejected_feedback = ""
    for filename in file_list:
        error = state.loop_metadata.get(f"rejected_fix_{filename}")
        if error:
            rejected_feedback += f"- **{filename}**: Previous patch REJECTED by system validator. Reason: {error}. Please provide a standard alternative.\n"
    
    if rejected_feedback:
        rejected_feedback = f"\n# ⚠️ System Warnings (Rejected Previous Fixes)\n{rejected_feedback}\n"

    prompt = f"""# Manifest
{json.dumps(manifest_info, indent=2, ensure_ascii=False)}

# Project Brief
{state.project_brief}

{rejected_feedback}

# 🎯 User Intent
{state.user_intent}

# 📚 Reference Materials
{state.reference_materials}

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
    
    if result and "verdict" in result:
        # Normalize verdict keys
        result["verdict"] = result["verdict"].upper()
        return result
    else:
        print("    [Critic] ❌ JSON Parse Error. Attempting salvage via Flash...")
        
        # SOTA: Emergency Salvage logic
        # We ask a lightweight model to just extract the JSON from the mess
        salvage_prompt = f"""The following text was generated by a technical editor but the JSON is malformed. 
Extract and fix the JSON. Ensure the output is ONLY a valid JSON object with 'verdict', 'feedback', and 'section_feedback' keys.

Malformed Text:
{text[:4000]}
"""
        try:
            salvage_resp = await client.generate_async(
                prompt=salvage_prompt,
                system_instruction="You are a JSON recovery expert. Output ONLY valid JSON.",
                temperature=0.0
            )
            if salvage_resp.success:
                salvaged_result = parse_json_dict_robust(salvage_resp.text)
                if salvaged_result and "verdict" in salvaged_result:
                    print("    [Critic] ✅ Salvage SUCCESS.")
                    salvaged_result["verdict"] = salvaged_result["verdict"].upper()
                    return salvaged_result
        except Exception as e:
            print(f"    [Critic] ❌ Salvage failed: {e}")

        # If salvage fails, log to file for human audit
        log_file = Path(state.workspace_path) / "debug_failed_critic_json.txt"
        log_file.write_text(text, encoding="utf-8")
        print(f"    [Critic] 📝 Raw failed output saved to {log_file}")

        # SOTA Safety: Default to MODIFY
        return {
            "verdict": "MODIFY", 
            "feedback": "Critical Error: AI output was not valid JSON even after salvage. Raw saved to workspace.",
            "section_feedback": {}
        }
