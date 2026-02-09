"""
Fixer Component for Markdown QA
Executes specific editing instructions on a target file.
"""

from typing import Dict, Optional, Any
from src.core.gemini_client import GeminiClient
from src.core.patcher import apply_smart_patch


FIXER_SYSTEM_PROMPT = r"""You are an expert code-editing assistant. 
Your task is to provide a \`search\` string that will match the text in the file precisely, and a \`replace\` string with the corrected content.

### Rules:
1. **Literal Matching**: The \`search\` field MUST be the EXACT literal text from the file, including all whitespace and indentation. Do not escape characters.
2. **Minimal Changes**: Only modify what is necessary to fix the issue.
3. **LaTeX Integrity**: Handle dollar signs ($) as regular characters. If the file has $$$$, your search block must have $$$$. Your replace block should have the correct count (e.g. $$).
4. **JSON Format**: Return ONLY a valid JSON object. Double-escape backslashes in the JSON (e.g. \\Phi).

```json
{
  "thought": "Reasoning for the search anchor choice.",
  "patches": [
    {
      "search": "exact text from file",
      "replace": "new text"
    }
  ]
}
```
"""

async def run_markdown_fixer(
    client: GeminiClient,
    file_content: str,
    advice: str,
    context: str = "",
    debug: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Run the Fixer to generate patches for a single file.
    """
    # Optimized Prompt Structure: Clear separation, reduced noise
    prompt = f"""# GOAL (The Fix to Apply)
{advice}

# TARGET FILE CONTENT (Read-Only Source)
{file_content}

# REFERENCE CONTEXT (Optional)
{context if context else "(None)"} 

---
Identify the text block to change and generate the JSON patch.
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
        error_msg = response.error or "(No error message, possibly timeout or empty response)"
        print(f"    [Fixer] ❌ API Failed: {error_msg}")
        return {"status": "FAILED", "reason": error_msg}
        
    text = response.text.strip()
    
    # robust parse
    from src.core.json_utils import parse_json_dict_robust
    result = parse_json_dict_robust(text)
    
    if not result or "patches" not in result:
        # 🧪 SOTA DEBUG: Save raw evidence
        import os
        from datetime import datetime
        debug_filename = f"debug_fixer_fail_{datetime.now().strftime('%H%M%S')}.txt"
        with open(debug_filename, "w", encoding="utf-8") as f:
            f.write(f"--- ADVICE ---\n{advice}\n\n--- RAW LLM TEXT ---\n{text}")
        
        print(f"    [Fixer] ⚠️ JSON Parse Error. Raw evidence saved to: {debug_filename}")
        print(f"    [Fixer] ⚠️ Snippet: {text[:100]}...")
        return {"status": "FAILED", "reason": "No valid JSON patches found"}
        
    return {"status": "FIXED", "patches": result["patches"]}

def apply_patches(original_content: str, result: Dict) -> str:
    """Apply patches using the Universal High-Precision Patcher."""
    if not result or result.get("status") != "FIXED":
        return original_content
        
    patches = result.get("patches", [])
    if not patches:
        return original_content
        
    modified_content = original_content
    for patch in patches:
        search_text = patch.get("search")
        replace_text = patch.get("replace")
        
        if search_text and replace_text is not None:
             # Use the Smart Patcher instead of simple string.replace
             new_content, success = apply_smart_patch(modified_content, search_text, replace_text)
             if success:
                 modified_content = new_content
             else:
                 # Fallback to simple replace if smart fails but search is exactly in content
                 if search_text in modified_content:
                     print(f"    [Fixer] 🔄 Smart patch failed, but exact match found. Falling back to exact replace for '{search_text[:30]}...'")
                     modified_content = modified_content.replace(search_text, replace_text, 1)
                 else:
                     print(f"    [Fixer] ❌ Patch failed: {new_content[:100]}...")
                 
    return modified_content