"""
Markdown Critic: Identifies content, logical, and structural issues in Markdown.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict
from ...core.gemini_client import GeminiClient
from ...core.types import AgentState
from ...core.debug_utils import save_debug_log

MARKDOWN_CRITIC_SYSTEM_PROMPT = """## Your Role: Markdown Technical Editor (Critic)
You are a world-class technical editor. Your ONLY job is to identify issues in technical Markdown documents.
You do NOT generate code fixes - just describe what's wrong as specific issues.

## Input Context
1. **Manifest**: The intended structure and knowledge points.
2. **Project Brief & SOTA Spec**: The quality and writing goals.
3. **Raw Materials**: The source of truth for facts.
4. **Available Files**: The list of Markdown files you can reference.
5. **Merged Markdown**: All sections with `<!-- [SOURCE:md/xxx.md] -->` markers.

## Your Focus
- **Logical Flow**: Does the narrative transition smoothly between sections?
- **Factual Accuracy**: Does it match the raw materials?
- **Knowledge Depth**: Does it meet the SOTA quality standards?
- **Formatting Consistency**: Are math formulas, code blocks, and diagrams used consistently?
- **Completeness**: Are all points from the Manifest covered?

## Output Schema (JSON)
```json
{
  "verdict": "PASS" | "FAIL",
  "issues": [
    {
      "id": "md-issue-1",
      "severity": "critical" | "major" | "minor",
      "location": "md/mod-02.md",
      "element": "Section Introduction",
      "problem": "The explanation of electric dipoles contradicts the raw material on page 5."
    }
  ]
}
```

## Rules
- Be pedantic. Quality is paramount.
- **CRITICAL**: The `location` field MUST be an EXACT file path from the Available Files list (e.g., "md/mod-01.md"). Do NOT use vague descriptions like "Throughout the document".
- If an issue spans multiple files, create separate issue entries for each file.
- If the document is ready for HTML generation, return "PASS".
"""

def run_markdown_critic(
    client: GeminiClient,
    state: AgentState,
    merged_content: str,
    debug: bool = False
) -> Optional[Dict]:
    """Analyze Markdown content and return issues."""
    
    manifest_info = {
        "project_title": state.manifest.project_title,
        "sections": [
            {"id": s.id, "title": s.title, "summary": s.summary}
            for s in state.manifest.sections
        ],
        "knowledge_map": state.manifest.knowledge_map
    }
    
    # Extract file list from state
    file_list = [Path(p).name for p in state.completed_md_sections]
    file_paths = [f"md/{f}" for f in file_list]
    
    prompt = f"""# Manifest (Expected Structure)
```json
{json.dumps(manifest_info, indent=2, ensure_ascii=False)}
```

# Project Brief
{state.project_brief}

# SOTA Specification
{state.manifest.description}

# Raw Materials (Source)
{state.raw_materials}

# Available Files (use these EXACT paths in the "location" field)
{json.dumps(file_paths, indent=2)}

# Merged Markdown Content (with markers)
{merged_content}

---

Identify any issues in the Markdown content based on the context above.
REMEMBER: Each issue's "location" MUST be one of the Available Files listed above.
"""

    print(f"    [MarkdownCritic] Prompt length: {len(prompt)} chars")
    # Structured output is causing issues with some proxies, falling back to text generation
    if False and hasattr(client, "generate_structured"):
        pass # Skip structured for now

    response = client.generate(
        prompt=prompt,
        system_instruction=MARKDOWN_CRITIC_SYSTEM_PROMPT,
        temperature=0.0,
        stream=False
    )

    if not response.success:
        error_msg = response.error or "(Empty response or unknown error)"
        print(f"    [MarkdownCritic] API Error: {error_msg}")
        return None

    try:
        text = response.text.strip()
        
        # Debug logging
        if debug:
            log_path = save_debug_log(
                workspace_path=state.workspace_path,
                agent_name="MarkdownCritic",
                step_name="critic_review",
                system_instruction=MARKDOWN_CRITIC_SYSTEM_PROMPT,
                prompt=prompt,
                response=text
            )
            print(f"    [MarkdownCritic] Debug log saved to {log_path.name}")

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        import re
        fixed_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)
        return json.loads(fixed_text)
    except Exception as e:
        print(f"    [MarkdownCritic] JSON Parse Error: {e}")
        return None
