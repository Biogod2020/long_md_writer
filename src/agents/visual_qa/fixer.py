"""Code Fixer Agent: Generates targeted fixes for individual issues."""

from pathlib import Path
from typing import Optional, Dict

from ...core.gemini_client import GeminiClient
from .prompts import FIXER_SYSTEM_PROMPT
from .utils import parse_json_response, add_line_numbers

def prepare_fixer_task(
    issue: Dict,
    section_path: str,
    workspace_path: str,
    style_mapping_path: Optional[str] = None
) -> Optional[Dict]:
    """Prepare task for Visual Fixer."""
    workspace = Path(workspace_path)
    section_code = Path(section_path).read_text(encoding="utf-8")
    
    css_code = ""
    css_path = workspace / "assets" / "style.css"
    if css_path.exists():
        css_code = css_path.read_text(encoding="utf-8")
    
    js_code = ""
    js_path = workspace / "assets" / "main.js"
    if js_path.exists():
        js_code = js_path.read_text(encoding="utf-8")
    
    style_mapping_content = ""
    if style_mapping_path and Path(style_mapping_path).exists():
        style_mapping_content = Path(style_mapping_path).read_text(encoding="utf-8")
    
    prompt = f"""# Issue to Fix

**ID**: {issue.get('id', 'unknown')}
**Severity**: {issue.get('severity', 'unknown')}
**Location**: PART {issue.get('location_part', '?')}
**Element**: {issue.get('element', 'unknown')}
**Problem**: {issue.get('problem', 'No description')}

# Source Files used for Rendering

## 1. html/{Path(section_path).name} (Section HTML)
```html
{add_line_numbers(section_code)}
```

## 2. assets/style.css (Global CSS)
```css
{add_line_numbers(css_code)}
```

## 3. assets/main.js (Global JS)
```javascript
{add_line_numbers(js_code) if js_code else "// empty"}
```

## 4. Design System Reference (Style Mapping)
Use this to identify correct CSS classes and components.
```json
{style_mapping_content}
```

# Task
Generate a fix for the visual issue described above. 
Analyze whether the issue is caused by the Section HTML, Global CSS, or Global JS.
Modify ONLY ONE file.
"""
    return {
        "prompt": prompt,
        "system_instruction": FIXER_SYSTEM_PROMPT,
        "temperature": 0.0,
        "issue_id": issue.get('id')
    }

def run_fixer(
    client: GeminiClient,
    issue: Dict,
    section_path: str,
    workspace_path: str,
    style_mapping_path: Optional[str] = None,
    debug_image_path: Optional[Path] = None,
    debug: bool = False
) -> Optional[str]: # Changed return type to str for raw response
    """
    Generate a fix for ONE specific issue, optionally using a debug image.
    Uses style_mapping.json for context instead of full appendices to reduce load.
    Returns the raw response text from the model.
    """
    
    task = prepare_fixer_task(issue, section_path, workspace_path, style_mapping_path)
    if not task:
        return None
        
    parts = []
    # Add debug image if provided
    if debug_image_path and debug_image_path.exists():
        try:
            from PIL import Image
            import io
            import base64
            with Image.open(debug_image_path) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                if img.width > 1200:
                    ratio = 1200 / img.width
                    img = img.resize((1200, int(img.height * ratio)), Image.Resampling.LANCZOS)
                
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80, optimize=True)
                image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image_data}})
            parts.append({"text": "[Debug Screenshot with Red Bounding Box highlighting the issue]"})
        except Exception as e:
            print(f"    [Fixer] Error loading debug image {debug_image_path}: {e}")

    parts.append({"text": task["prompt"]})
    
    # Retry logic for API 500 errors
    MAX_RETRIES = 3
    import time
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.generate(
                parts=parts,  # Use parts instead of prompt string
                system_instruction=FIXER_SYSTEM_PROMPT,
                temperature=0.0,
                stream=True  # 启用流式生成以避免 500 超时
            )
            
            if debug:
                print(f"\n    [Fixer Debug] Raw Response:\n{'-'*40}\n{response.text}\n{'-'*40}")
            
            if not response.success:
                print(f"    [Fixer] API Error (attempt {attempt+1}/{MAX_RETRIES}): {response.error}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                    print(f"    [Fixer] Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                return None
            
            return parse_json_response(response.text)
        except Exception as e:
            print(f"    [Fixer] Exception (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    
    return None

def apply_fix(fix_result: Dict, workspace_path: str) -> bool:
    """
    Apply a single fix from the Fixer agent.
    
    Returns True if fix was applied successfully.
    """
    workspace = Path(workspace_path)
    target_file_rel = fix_result.get("target_file")
    fix = fix_result.get("fix", {})
    
    if not target_file_rel:
        return False
    
    target_file = workspace / target_file_rel
    if not target_file.exists():
        print(f"    [Fixer] Target file not found: {target_file_rel}")
        return False
    
    content = target_file.read_text(encoding="utf-8")
    fix_type = fix.get("type")
    
    if fix_type == "replace":
        target = fix.get("target")
        replacement = fix.get("replacement")
        
        if not target or target not in content:
            print(f"    [Fixer] Target string not found in {target_file_rel}")
            return False
        
        count = content.count(target)
        if count > 1:
            print(f"    [Fixer] Ambiguous target ({count} matches). Skipping.")
            return False
        
        content = content.replace(target, replacement, 1)
        target_file.write_text(content, encoding="utf-8")
        return True
        
    elif fix_type == "append":
        new_content = fix.get("content")
        location = fix.get("location", "end")
        if new_content:
            if location == "end":
                content = content.rstrip() + "\n" + new_content + "\n"
            else:
                content = new_content + "\n" + content
            target_file.write_text(content, encoding="utf-8")
            return True
            
    elif fix_type == "delete":
        target = fix.get("target")
        if target and target in content:
            content = content.replace(target, "")
            target_file.write_text(content, encoding="utf-8")
            return True
    
    return False
