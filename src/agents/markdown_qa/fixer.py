"""
Fixer Component for Markdown QA
Executes specific editing instructions on a target file.
"""

from typing import Dict, Optional, Any, Union, List
import json
from src.core.gemini_client import GeminiClient
from src.core.patcher import apply_smart_patch

def add_line_numbers(code: str) -> str:
    """Add line numbers to code for AI reference."""
    lines = code.split('\n')
    width = len(str(len(lines)))
    return '\n'.join(f"{str(i+1).rjust(width)} | {line}" for i, line in enumerate(lines))


FIXER_SYSTEM_PROMPT = r"""You are an expert code-editing assistant. 
Your task is to implement hierarchical patches based on the provided instructions.

### Scopes:
1. **GLOBAL**: Simple search/replace applied to ALL occurrences in the document. No context needed.
2. **TARGETED**: Precise search/replace for a specific location. You MUST match the EXACT literal text from the file including all whitespace.

### Rules:
1. **Literal Matching**: For TARGETED, the \`search\` field MUST be the EXACT literal text.
2. **Minimal Changes**: Only modify what is necessary.
3. **JSON Format**: Return ONLY valid JSON. Double-escape backslashes.

```json
{
  "thought": "Reasoning...",
  "patches": [
    {
      "scope": "GLOBAL",
      "search": "Φ",
      "replace": "φ"
    },
    {
      "scope": "TARGETED",
      "search": "exact context lines...",
      "replace": "new lines..."
    }
  ]
}
```
"""

async def run_markdown_fixer(
    client: GeminiClient,
    file_content: str,
    advice: Union[str, List[Dict]],
    context: str = "",
    debug: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Run the Fixer to generate patches. Supports both legacy string advice 
    and the new hierarchical instruction list.
    """
    if isinstance(advice, list):
        advice_text = json.dumps(advice, indent=2, ensure_ascii=False)
    else:
        advice_text = advice

    prompt = f"""# 🛠️ MISSION: APPLY HIERARCHICAL PATCHES
Apply the following changes to the target file.

## 📋 HIERARCHICAL INSTRUCTIONS
{advice_text}

## 📄 TARGET FILE CONTENT (Line numbers for reference only)
```markdown
{add_line_numbers(file_content)}
```

## 🔍 ADDITIONAL CONTEXT
<details>
{context if context else "(None)"}
</details>

---
Generate the JSON patch. Use "scope": "GLOBAL" for general replacements and "scope": "TARGETED" for specific structural fixes.
"""
    
    if debug:
        print(f"    [Fixer] Prompt size: {len(prompt)} chars")
        
    response = await client.generate_async(
        prompt=prompt,
        system_instruction=FIXER_SYSTEM_PROMPT,
        temperature=0.0,
        stream=True
    )
    
    if not response.success:
        error_msg = response.error or "(No error message)"
        print(f"    [Fixer] ❌ API Failed: {error_msg}")
        return {"status": "FAILED", "reason": error_msg}
        
    # robust parse
    from src.core.json_utils import parse_json_dict_robust
    result = parse_json_dict_robust(response.text)
    
    if not result or "patches" not in result:
        return {"status": "FAILED", "reason": "No valid JSON patches found"}
        
    return {"status": "FIXED", "patches": result["patches"]}

def apply_patches(original_content: str, result: Dict) -> str:
    """Apply patches supporting GLOBAL and TARGETED scopes."""
    if not result or result.get("status") != "FIXED":
        return original_content
        
    patches = result.get("patches", [])
    if not patches:
        return original_content
        
    modified_content = original_content
    for patch in patches:
        scope = patch.get("scope", "TARGETED") # Default to targeted for safety
        search_text = patch.get("search")
        replace_text = patch.get("replace")
        
        if not search_text or replace_text is None:
            continue

        if scope == "GLOBAL":
            # Global simple replacement
            if search_text in modified_content:
                count = modified_content.count(search_text)
                modified_content = modified_content.replace(search_text, replace_text)
                print(f"    [Fixer] 🌍 Global replacement applied to {count} occurrences: '{search_text}' -> '{replace_text}'")
        else:
            # Targeted smart patch
            new_content, success = apply_smart_patch(modified_content, search_text, replace_text)
            if success:
                modified_content = new_content
            else:
                # Fallback
                if search_text in modified_content:
                    print(f"    [Fixer] 🔄 Smart patch failed, but exact match found. Falling back to exact replace.")
                    modified_content = modified_content.replace(search_text, replace_text, 1)
                else:
                    print(f"    [Fixer] ❌ Patch failed for anchor: {search_text[:50]}...")
                 
    return modified_content