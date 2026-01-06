"""
Markdown Fixer: Applies targeted fixes to Markdown files using Search/Replace pattern.
"""

from pathlib import Path
from typing import Optional, Dict, List
import json
import re

from ...core.gemini_client import GeminiClient
from ...core.debug_utils import save_debug_log

MARKDOWN_FIXER_SYSTEM_PROMPT = """## Your Role: Markdown Content Fixer
You receive ONE content issue in a Markdown file and must generate a precise fix.

## The Search/Replace Pattern
You MUST provide the fix in a SEARCH/REPLACE block style. This is extremely important for precision.

### Format:
```json
{
  "status": "FIXED",
  "target_file": "md/slide-1.md",
  "fix": {
    "type": "replace",
    "search": "<exact existing block of text to find>",
    "replace": "<new text to replace it with>"
  },
  "explanation": "Fixed the factual error regarding X."
}
```

## Rules for SEARCH/REPLACE:
1. **Uniqueness**: The `search` block MUST be completely unique in the file to avoid multiple matches.
2. **Precision**: Include enough surrounding context (lines before/after) to ensure it is unique.
3. **Exact Match**: The `search` block must match the original text EXACTLY, including all indentation, whitespace, and punctuation. DO NOT summarize or skip any part of the text you are replacing.
4. **Minimal Change**: Only change what is necessary to resolve the issue.

## Fix Types
- `replace`: Use for modifying, deleting, or expanding specific sections.
- `append`: (Fallback) If you just need to add something to the "start" or "end" of the file.

### Example for Append:
```json
{ "type": "append", "location": "end", "content": "## Appendix\\n..." }
```

## Guidelines
- If the issue cannot be fixed automatically or requires user clarification, return:
  `{"status": "SKIPPED", "reason": "Detailed reason why"}`
- **CRITICAL**: You MUST return a VALID JSON block inside ```json``` fences. 
- Do NOT output any text outside the JSON block.
"""

def prepare_markdown_fixer_task(
    issue: Dict,
    md_file_path: str,
    workspace_path: str
) -> Optional[Dict]:
    """Prepare the task definition for parallel execution."""
    file_path = Path(workspace_path) / md_file_path
    if not file_path.exists():
        return None
        
    content = file_path.read_text(encoding="utf-8")
    lines = content.split('\n')
    numbered_content = '\n'.join(f"{i+1:4} | {line}" for i, line in enumerate(lines))
    
    prompt = f"""# Issue to Resolve
**Location**: {issue.get('location', 'unknown')}
**Element**: {issue.get('element', 'unknown')}
**Problem**: {issue.get('problem', 'unknown')}

# File: {md_file_path} (with reference line numbers)
```markdown
{numbered_content}
```

# Instructions
Provide a SEARCH/REPLACE block to fix the issue. 
The SEARCH block must be UNIQUE and match the file EXACTLY (excluding the line numbers provided above).
"""
    return {
        "prompt": prompt,
        "system_instruction": MARKDOWN_FIXER_SYSTEM_PROMPT,
        "temperature": 0.0,
        "issue_id": issue.get('id'), # Metadata for tracking
        "target_file": md_file_path
    }

def parse_markdown_fixer_response(text: str) -> Optional[Dict]:
    """Parse the raw response from the Fixer agent."""
    try:
        if not text:
            return None

        clean_text = text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
             clean_text = clean_text.split("```")[1].split("```")[0].strip()
        
        # Robust cleanup
        # Remove JS comments // ...
        clean_text = re.sub(r'^\s*//.*$', '', clean_text, flags=re.MULTILINE)
        # Escape backslashes that are not part of known escape sequences
        fixed_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', clean_text)
        
        return json.loads(fixed_text)
    except Exception as e:
        print(f"    [MarkdownFixer] Parse Error: {e}")
        return None

def run_markdown_fixer(
    client: GeminiClient,
    issue: Dict,
    md_file_path: str,
    workspace_path: str,
    debug: bool = False
) -> Optional[Dict]:
    """Generate a fix for a specific Markdown issue (Sequential Mode)."""
    
    task = prepare_markdown_fixer_task(issue, md_file_path, workspace_path)
    if not task:
        return {"status": "SKIPPED", "reason": f"File {md_file_path} not found"}
    
    # Retry logic for API 500 errors
    MAX_RETRIES = 3
    import time
    
    parts = [{"text": task["prompt"]}]
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.generate(
                prompt=task["prompt"],
                system_instruction=task["system_instruction"],
                temperature=task["temperature"],
                stream=False
            )

            if not response.success:
                print(f"    [MarkdownFixer] API Error (attempt {attempt+1}/{MAX_RETRIES}): {response.error}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

            text = response.text
            
            # Debug logging
            if debug:
                save_debug_log(
                    workspace_path=workspace_path,
                    agent_name="MarkdownFixer",
                    step_name=f"fix_{issue.get('id', 'unknown')}_attempt_{attempt+1}",
                    system_instruction=task["system_instruction"],
                    prompt=parts,
                    response=text
                )

            result = parse_markdown_fixer_response(text)
            if result:
                return result
                
        except Exception as e:
            print(f"    [MarkdownFixer] Exception (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    
    return None

def apply_markdown_fix(fix_result: Dict, workspace_path: str) -> bool:
    """Apply a single SEARCH/REPLACE fix to a Markdown file."""
    workspace = Path(workspace_path)
    target_rel = fix_result.get("target_file")
    fix = fix_result.get("fix", {})
    
    if not target_rel or not fix:
        return False
        
    target_file = workspace / target_rel
    if not target_file.exists():
        print(f"    [MarkdownFixer] File not found: {target_rel}")
        return False
        
    content = target_file.read_text(encoding="utf-8")
    fix_type = fix.get("type", "replace")
    
    if fix_type == "replace":
        search_block = fix.get("search")
        replace_block = fix.get("replace")
        
        if not search_block:
            print(f"    [MarkdownFixer] Missing search block in {target_rel}")
            return False
            
        if search_block not in content:
            print(f"    [MarkdownFixer] Search block not found in {target_rel}")
            return False
            
        count = content.count(search_block)
        if count > 1:
            print(f"    [MarkdownFixer] Search block is not unique ({count} matches) in {target_rel}")
            return False
            
        new_content = content.replace(search_block, replace_block, 1)
        target_file.write_text(new_content, encoding="utf-8")
        return True
        
    elif fix_type == "append":
        new_content = fix.get("content")
        location = fix.get("location", "end")
        if new_content:
            if location == "end":
                content = content.rstrip() + "\n\n" + new_content + "\n"
            else:
                content = new_content + "\n\n" + content
            target_file.write_text(content, encoding="utf-8")
            return True
            
    return False
