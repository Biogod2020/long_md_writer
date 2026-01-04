"""
MarkdownQAAgent: Reviews all Markdown sections against Manifest and Raw Materials.
Uses the same fix logic as VisualQAAgent (replace/append/delete).
"""

import json
from pathlib import Path
from typing import Optional, List, Dict

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


MARKDOWN_QA_SYSTEM_PROMPT = '''You are a **world-class technical editor** with expertise in:
- Scientific and technical writing
- Markdown syntax and best practices
- Content structure and logical flow
- Fact-checking against source materials

## Your Task
You will receive:
1. **Manifest (Expected Structure)**: JSON defining sections, titles, and knowledge points.
2. **Raw Materials**: Original source content and user requirements.
3. **Merged Markdown**: All generated sections combined (with `<!-- [SOURCE:md/sec-X.md] -->` markers).
4. **Editable Files**: List of Markdown files you can suggest fixes for.

## Instructions
1. **Verify Structure**: Ensure all manifest sections exist with correct titles.
2. **Check Completeness**: Verify key knowledge points from raw materials are covered.
3. **Assess Quality**: Logical flow, clear explanations, proper Markdown syntax.
4. **Generate Fixes**: Use the JSON schema below. Target specific source files.

## Output Schema (JSON)
```json
{
  "overall_verdict": "PASS" | "FAIL",
  "issues": [
    {
      "severity": "critical" | "major" | "minor",
      "description": "Section sec-3 is missing the concept of X from raw materials.",
      "source_file": "md/sec-3.md",
      "fix": {
        "type": "replace",
        "target": "## 小结",
        "replacement": "## X 的核心原理\\n\\n[内容关于X]\\n\\n## 小结"
      }
    }
  ],
  "summary": "Summary of findings."
}
```

## Fix Types
- `replace`: Find exact `target` string and replace with `replacement`.
- `append`: Add `content` at `location` ("start" or "end" of file).
- `delete`: Remove exact `target` string.

## Critical Rules
- **Source files only**: Only reference files from the provided editable list.
- **Conservative**: Flag only clear issues, not stylistic preferences.
- **Minimal diffs**: Target the smallest change that fixes the issue.
- If quality is acceptable, return `"overall_verdict": "PASS"` with empty issues.
'''


class MarkdownQAAgent:
    """Agent that reviews Markdown quality and applies targeted fixes."""

    def __init__(self, client: Optional[GeminiClient] = None, max_iterations: int = 3):
        self.client = client or GeminiClient()
        self.max_iterations = max_iterations
        self.model_name = "gemini-3-flash-preview-maxthinking"

    def run(self, state: AgentState) -> AgentState:
        """Execute Markdown QA and repair loop."""
        if not state.completed_md_sections:
            print("  [MarkdownQA] No Markdown sections to review.")
            return state

        # Track iterations to prevent infinite loops
        iteration = getattr(state, "md_qa_iterations", 0)
        if iteration >= self.max_iterations:
            print(f"  [MarkdownQA] Reached max iterations ({self.max_iterations}). Skipping.")
            state.md_qa_needs_revision = False
            return state

        state.md_qa_iterations = iteration + 1
        print(f"  [MarkdownQA] Starting iteration {state.md_qa_iterations}...")

        # 1. Merge all Markdown with source markers
        merged_content = self._merge_with_markers(state)

        # 2. Get list of editable files
        file_list = self._list_editable_files(state)

        # 3. Get VLM critique
        response = self._get_critique(state, merged_content, file_list)
        if not response:
            state.errors.append("MarkdownQAAgent: Failed to get response from VLM.")
            state.md_qa_needs_revision = False
            return state

        # 4. Handle results
        verdict = response.get("overall_verdict", "PASS")
        print(f"  [MarkdownQA] Verdict: {verdict}")

        if verdict == "FAIL":
            issues = response.get("issues", [])
            modified = self._apply_fixes(state, issues)

            if modified:
                print(f"  [MarkdownQA] Applied fixes. Requesting re-check.")
                state.md_qa_needs_revision = True
            else:
                print(f"  [MarkdownQA] VLM suggested fixes but none could be applied.")
                state.md_qa_needs_revision = False
        else:
            print(f"  [MarkdownQA] Quality check passed.")
            state.md_qa_needs_revision = False

        return state

    def _merge_with_markers(self, state: AgentState) -> str:
        """Merge all Markdown sections with source file markers."""
        parts = []
        for md_path in state.completed_md_sections:
            try:
                content = Path(md_path).read_text(encoding="utf-8")
                filename = Path(md_path).name
                marked = f"<!-- [SOURCE:md/{filename}] -->\n{content}\n<!-- [/SOURCE:md/{filename}] -->"
                parts.append(marked)
            except Exception as e:
                parts.append(f"<!-- Error reading {md_path}: {e} -->")
        return "\n\n".join(parts)

    def _list_editable_files(self, state: AgentState) -> List[str]:
        """List Markdown files that VLM can suggest fixes for."""
        return [f"md/{Path(p).name}" for p in state.completed_md_sections]

    def _get_critique(self, state: AgentState, merged: str, file_list: List[str]) -> Optional[Dict]:
        """Send merged Markdown to VLM for review."""
        # Prepare manifest info
        manifest_info = {
            "project_title": state.manifest.project_title,
            "sections": [
                {"id": s.id, "title": s.title, "summary": s.summary}
                for s in state.manifest.sections
            ],
            "knowledge_map": state.manifest.knowledge_map
        }

        prompt = f"""# Manifest (Expected Structure)
```json
{json.dumps(manifest_info, indent=2, ensure_ascii=False)}
```

# Raw Materials (Source)
{state.raw_materials[:50000]}

# Editable Files
{json.dumps(file_list, indent=2)}

# Merged Markdown Content (with markers)
{merged[:100000]}

Please review the Markdown content and provide your assessment.
"""

        try:
            response = self.client.generate(
                prompt=prompt,
                system_instruction=MARKDOWN_QA_SYSTEM_PROMPT,
                temperature=0.0
            )

            if not response.success:
                print(f"  [MarkdownQA] VLM Error: {response.error}")
                return None

            # Parse JSON from response
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            
            # Pre-process: common LaTeX escape issues in JSON
            # Replace single backslashes with double backslashes unless they are already escaped
            import re
            fixed_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)

            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                # Fallback to original text if regex failed
                return json.loads(text)
        except Exception as e:
            print(f"  [MarkdownQA] Failed to parse VLM response: {e}")
            return None

    def _apply_fixes(self, state: AgentState, issues: List[Dict]) -> bool:
        """Apply the suggested fixes to the source files (same logic as VisualQA)."""
        modified = False
        workspace = Path(state.workspace_path)

        for issue in issues:
            severity = issue.get("severity", "minor")
            if severity == "minor":
                continue

            source_file_rel = issue.get("source_file")
            if not source_file_rel:
                continue

            source_file = workspace / source_file_rel
            if not source_file.exists():
                print(f"  [MarkdownQA] Warning: Suggested file {source_file_rel} not found.")
                continue

            content = source_file.read_text(encoding="utf-8")
            fix = issue.get("fix", {})
            fix_type = fix.get("type")

            if fix_type == "replace":
                target = fix.get("target")
                replacement = fix.get("replacement")
                if target and replacement and target in content:
                    content = content.replace(target, replacement, 1)
                    modified = True
                    print(f"  [MarkdownQA] Replaced content in {source_file_rel}")
                else:
                    print(f"  [MarkdownQA] Could not find target for replacement in {source_file_rel}")

            elif fix_type == "append":
                new_content = fix.get("content")
                location = fix.get("location", "end")
                if new_content:
                    if location == "end":
                        content = content.rstrip() + "\n\n" + new_content + "\n"
                    else:
                        content = new_content + "\n\n" + content
                    modified = True
                    print(f"  [MarkdownQA] Appended content to {source_file_rel}")

            elif fix_type == "delete":
                target = fix.get("target")
                if target and target in content:
                    content = content.replace(target, "")
                    modified = True
                    print(f"  [MarkdownQA] Deleted content from {source_file_rel}")

            if modified:
                source_file.write_text(content, encoding="utf-8")

        return modified


def create_markdown_qa_agent(client: Optional[GeminiClient] = None) -> MarkdownQAAgent:
    """Create MarkdownQAAgent instance."""
    return MarkdownQAAgent(client=client)
