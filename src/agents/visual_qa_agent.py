"""
VisualQAAgent: Uses VLM to check the rendered HTML and apply targeted fixes.
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from DrissionPage import ChromiumOptions, ChromiumPage

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState
from ..core.json_utils import parse_json_dict_robust


CRITIC_SYSTEM_PROMPT = """## Your Role: Visual Critic
You are a visual QA specialist. Your ONLY job is to identify visual issues in HTML screenshots.
You do NOT generate code fixes - just describe what's wrong.

## Input
1. **Screenshots**: Sequential screenshots with overlap (200px). Red badges show "PART X | Scroll: Ypx".
2. **Section HTML**: Source code with line numbers for reference.
3. **Global CSS/JS**: The stylesheet and scripts applied to this section.

## Output Schema (JSON)
```json
{
  "verdict": "PASS" | "FAIL",
  "issues": [
    {
      "id": "issue-1",
      "severity": "critical" | "major" | "minor",
      "location": "PART 2, around scroll 800px, near the SVG diagram",
      "element": "The formula V_ecg in the SVG",
      "problem": "The subscript 'ecg' is rendered as underscore instead of proper subscript"
    }
  ]
}
```

## Rules
- Keep descriptions SHORT and SPECIFIC
- Reference PART numbers and scroll positions from the red badges
- Focus on VISUAL bugs only (layout, rendering, typography, spacing)
- If everything looks correct, return {"verdict": "PASS", "issues": []}
"""

FIXER_SYSTEM_PROMPT = """## Your Role: Code Fixer
You receive ONE visual issue and must generate a precise fix.

## Input
- Issue description with location hint
- Source file content (HTML, CSS, or JS)
- Line numbers for reference

## Output Schema (JSON)
```json
{
  "status": "FIXED",
  "target_file": "html/sec-1.html",
  "fix": {
    "type": "replace",
    "target": "<exact unique string to find>",
    "replacement": "<corrected string>"
  },
  "explanation": "Changed X to Y because..."
}
```

## Fix Types
- `replace`: Find and replace exact string (must be UNIQUE in file)
- `append`: Add content at "start" or "end" of file
- `delete`: Remove exact string

## Rules
- The `target` MUST be unique in the file - include enough context
- Return `{"status": "SKIPPED", "reason": "..."}` if you cannot fix this issue
- Only modify ONE thing per fix
"""

class VisualQAAgent:
    """Agent that performs visual inspection and automated repairs."""

    def __init__(self, client: Optional[GeminiClient] = None, debug: bool = False, headless: bool = True):
        self.client = client or GeminiClient()
        self.debug = debug
        self.headless = headless
        self.max_iterations = 3
        self.model_name = "gemini-3-flash-preview-maxthinking"

    def run(self, state: AgentState) -> AgentState:
        """Execute visual QA using Critic-Fixer dual-agent architecture."""
        if not state.completed_html_sections:
            print("  [VisualQA] No HTML sections to check.")
            return state

        print(f"  [VisualQA] Starting Critic-Fixer Loop (no iteration limit for testing)...")

        any_modified = False
        workspace = Path(state.workspace_path)

        for section_path in state.completed_html_sections:
            section_name = Path(section_path).name
            section_rel = f"html/{section_name}"
            print(f"\n  [VisualQA] 🔍 Processing: {section_rel}")
            
            iteration = 0
            while True:  # No limit for testing
                iteration += 1
                print(f"\n    [Iteration {iteration}] Running Visual Critic...")
                
                # Step 1: Critic reviews screenshots
                critique = self._run_critic(state, section_path)
                
                if critique is None:
                    print(f"    [Critic] ⚠️ Error during critique. Moving to next section.")
                    break
                
                if critique.get("verdict") == "PASS":
                    print(f"    [Critic] ✅ Section PASSED after {iteration} iteration(s).")
                    break
                
                issues = critique.get("issues", [])
                if not issues:
                    print(f"    [Critic] ✅ No issues found. PASSED.")
                    break
                
                print(f"    [Critic] Found {len(issues)} issue(s):")
                for issue in issues:
                    print(f"      - [{issue.get('severity', 'unknown')}] {issue.get('problem', 'No description')}")
                
                # Step 2: Fixer addresses each issue
                if hasattr(self.client, "generate_parallel"):
                     print(f"    [VisualQA] 🚀 Using Parallel Execution for {len(issues)} fixes...")
                     from .visual_qa.fixer import prepare_fixer_task
                     from .visual_qa.utils import parse_json_response
                     
                     tasks = []
                     valid_issues = []
                     
                     # 1. Prepare all tasks
                     for issue in issues:
                         task = prepare_fixer_task(
                             issue=issue,
                             section_path=section_path,
                             workspace_path=state.workspace_path,
                             style_mapping_path=str(Path(state.workspace_path) / "style_mapping.json")
                         )
                         if task:
                             tasks.append(task)
                             valid_issues.append(issue)
                     
                     if tasks:
                         try:
                             # 2. Execute parallel
                             responses = self.client.generate_parallel(tasks)
                             
                             # 3. Process results
                             fixes_applied = 0
                             for i, response in enumerate(responses):
                                 issue = valid_issues[i]
                                 if not response.success:
                                     print(f"    [Fixer] ❌ Failed to fix issue {issue.get('id')}: {response.error}")
                                     continue
                                     
                                 fix_result = parse_json_response(response.text)
                                 if fix_result and fix_result.get("status") == "FIXED":
                                     # Need to inject target_file if missing or wrong relative path
                                     # The prompt asks for it, but let's be safe
                                     
                                    print(f"    [Fixer] Applying fix for {issue.get('id')}...")
                                    applied = self._apply_single_fix(state, fix_result)
                                    if applied:
                                        fixes_applied += 1
                                        any_modified = True
                                        print(f"      ✅ Fixed {fix_result.get('target_file')}")
                                 else:
                                    reason = fix_result.get("reason", "Unknown") if fix_result else "Parse Error"
                                    print(f"    [Fixer] ⏭️ Skipped {issue.get('id')}: {reason}")
                                    
                         except Exception as e:
                             print(f"    [VisualQA] Parallel Fixer Error: {e}")
                             fixes_applied = 0
                     else:
                        fixes_applied = 0

                else:
                    # Sequential Fallback
                    print(f"    [VisualQA] Running sequential fixes...")
                    fixes_applied = 0
                    for issue in issues:
                        print(f"\n    [Fixer] Addressing: {issue.get('id', 'unknown')}")
                        fix_result = self._run_fixer(state, section_path, issue)
                        
                        if fix_result and fix_result.get("status") == "FIXED":
                            applied = self._apply_single_fix(state, fix_result)
                            if applied:
                                fixes_applied += 1
                                any_modified = True
                                print(f"    [Fixer] ✅ Applied fix to {fix_result.get('target_file')}")
                        else:
                            reason = fix_result.get("reason", "Unknown") if fix_result else "No response"
                            print(f"    [Fixer] ⏭️ Skipped: {reason}")
                
                if fixes_applied == 0:
                    print(f"    [Iteration {iteration}] No fixes applied. Breaking to avoid infinite loop.")
                    break
                
                print(f"    [Iteration {iteration}] Applied {fixes_applied} fix(es). Re-rendering...")
                # Re-generate preview for next iteration
                self._regenerate_section_preview(state, section_path)

        if any_modified:
            print(f"\n  [VisualQA] Files were modified. Requesting re-assembly.")
            state.vqa_needs_reassembly = True
        else:
            print(f"\n  [VisualQA] All sections processed. No modifications needed.")
            state.vqa_needs_reassembly = False

        return state

        return state

    def _process_section(self, state: AgentState, section_path: str, file_list: List[str]) -> str:
        """
        Process a single section.
        Returns: "PASS", "MODIFIED", "FAIL", "ERROR"
        """
        # 1. Create temporary standalone test page for this section
        test_html_path = self._prepare_section_test_page(state, section_path)
        if not test_html_path:
            return "ERROR"

        # 2. Take screenshots of this section
        screenshot_paths = self._take_screenshots_of_path(test_html_path, state.workspace_path)
        if not screenshot_paths:
            if test_html_path.exists(): test_html_path.unlink()
            return "ERROR"

        # 3. Get VLM Critique
        section_code = Path(section_path).read_text(encoding="utf-8")
        workspace = Path(state.workspace_path)
        
        css_code = ""
        if (workspace / "assets" / "style.css").exists():
            css_code = (workspace / "assets" / "style.css").read_text(encoding="utf-8")
            
        js_code = ""
        if (workspace / "assets" / "main.js").exists():
            js_code = (workspace / "assets" / "main.js").read_text(encoding="utf-8")

        # Compile appendices (other sections) - OPTIMIZED: Headers Only to verify structure/continuity without massive payload
        appendices = []
        import re
        header_pattern = re.compile(r'<h[1-4][^>]*>(.*?)</h[1-4]>', re.IGNORECASE)
        
        for other_path in state.completed_html_sections:
            if other_path != section_path:
                try:
                    name = Path(other_path).name
                    full_text = Path(other_path).read_text(encoding="utf-8")
                    
                    # Extract only headers to build a skeleton
                    headers = header_pattern.findall(full_text)
                    structure = "\n".join([f"- {h.strip()}" for h in headers])
                    
                    if not structure:
                        structure = "(No headers found)"
                        
                    appendices.append(f"--- APPENDIX: {name} (Structure Only) ---\n{structure}\n")
                except:
                    pass
        appendix_text = "\n".join(appendices)

        response = self._get_vlm_critique_modular_with_retry(
            screenshot_paths=screenshot_paths,
            section_name=Path(section_path).name,
            section_code=section_code,
            css_code=css_code,
            js_code=js_code,
            appendix_text=appendix_text,
            file_list=file_list
        )
        
        # Cleanup temp HTML
        if test_html_path.exists():
            test_html_path.unlink()

        if not response:
            return "ERROR"

        # 4. Apply Fixes
        verdict = response.get("overall_verdict", "PASS")
        if verdict == "FAIL":
            issues = response.get("issues", [])
            if not issues:
                return "PASS" # False alarm
                
            modified = self._apply_fixes(state, issues)
            return "MODIFIED" if modified else "FAIL"
        
        return "PASS"

    def _get_vlm_critique_modular_with_retry(self, screenshot_paths: List[Path], section_name: str, 
                                 section_code: str, css_code: str, js_code: str, 
                                 appendix_text: str, file_list: List[str]) -> Optional[Dict]:
        """Retry wrapper for VLM calls to handle 500 errors by reducing payload."""
        
        # Strategy 1: Full Payload
        res = self._get_vlm_critique_modular(screenshot_paths, section_name, section_code, css_code, js_code, appendix_text, file_list)
        if res: return res
        
        print("    [VisualQA] ⚠️ First attempt failed (likely 500/Overload). Retrying with reduced screenshots...")
        
        # Strategy 2: Reduced Screenshots (Only first and last if > 2)
        if len(screenshot_paths) > 2:
            reduced_paths = [screenshot_paths[0], screenshot_paths[-1]]
            res = self._get_vlm_critique_modular(reduced_paths, section_name, section_code, css_code, js_code, appendix_text, file_list)
            if res: return res
            
        print("    [VisualQA] ⚠️ Second attempt failed. Retrying with NO screenshots (Code-only Mode)...")
        
        # Strategy 3: Code Only (Last resort)
        res = self._get_vlm_critique_modular([], section_name, section_code, css_code, js_code, appendix_text, file_list)
        return res

    def _get_vlm_critique_modular(self, screenshot_paths: List[Path], section_name: str, 
                                 section_code: str, css_code: str, js_code: str, 
                                 appendix_text: str, file_list: List[str]) -> Optional[Dict]:
        """Specific multi-screenshot request for a single section with global context."""
        prompt = f"""# Inspecting Section: {section_name}

# Editable Files
{json.dumps(file_list, indent=2)}

        # Current Section HTML Source ({section_name})
# (Line numbers added for reference only. Do NOT include line numbers in 'target' or 'replacement')
```html
{self._add_line_numbers(section_code)}
```

# Global CSS (assets/style.css)
```css
{css_code}
```

# Global JS (assets/main.js)
```javascript
{js_code}
```

# Other Sections Context (Appendices)
{appendix_text}

# Instructions
Attached are {len(screenshot_paths)} screenshots of the rendered "{section_name}".
Please identify visual bugs in this section and suggest fixes for either the section HTML or the global assets.
"""
        
        parts = []
        import base64
        import io
        from PIL import Image

        for i, path in enumerate(screenshot_paths):
            try:
                # Resize and compress image
                with Image.open(path) as img:
                    # Convert to RGB (in case of PNG alpha channel)
                    if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
                    
                    # Resize if too large (max width 1200)
                    if img.width > 1200:
                        ratio = 1200 / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((1200, new_height), Image.Resampling.LANCZOS)
                    
                    # Save to buffer as JPEG with 80% quality
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=80, optimize=True)
                    image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    parts.append({
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_data
                        }
                    })
                parts.append({"text": f"[Screenshot Part {i+1} of Section {section_name}]"})
            except Exception as e:
                print(f"  [VisualQA] Error processing image {path}: {e}")

        parts.append({"text": prompt})

        try:
            response = self.client.generate(
                parts=parts,
                system_instruction=VISUAL_QA_SYSTEM_PROMPT,
                temperature=0.0
            )
            
            if self.debug:
                print(f"\n  [VisualQA Debug] Raw API Response:\n{'-'*40}\n{response.text}\n{'-'*40}\n")
            
            if not response.success:
                print(f"  [VisualQA] VLM Error: {response.error}")
                return None
                
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            
            import re
            fixed_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)

            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                return json.loads(text)
        except Exception as e:
            print(f"  [VisualQA] Failed modular VLM call: {e}")
            return None

    def _add_line_numbers(self, code: str) -> str:
        """Helper to add line numbers for VLM reference."""
        lines = code.split('\n')
        width = len(str(len(lines)))
        return '\n'.join(f"{str(i+1).rjust(width)} | {line}" for i, line in enumerate(lines))

    def _prepare_section_test_page(self, state: AgentState, section_path: str) -> Optional[Path]:
        """Create a full HTML page for a single section to render it correctly with styles."""
        try:
            section_content = Path(section_path).read_text(encoding="utf-8")
            workspace_path = Path(state.workspace_path)
            
            # Simple template that mirrors the main structure
            template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="assets/style.css">
    <!-- KaTeX for math rendering -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
</head>
<body class="main-content">
    <article class="article">
        {section_content}
    </article>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: "$$", right: "$$", display: true}},
                    {{left: "$", right: "$", display: false}}
                ]
            }});
        }});
    </script>
    <script src="assets/main.js"></script>
</body>
</html>"""
            
            test_html_path = workspace_path / f"temp_vqa_{Path(section_path).stem}.html"
            test_html_path.write_text(template, encoding="utf-8")
            return test_html_path
        except Exception as e:
            print(f"  [VisualQA] Error preparing test page: {e}")
            return None

    def _take_screenshots_of_path(self, html_path: Path, workspace_path: str) -> List[Path]:
        """Capture screenshots of a specific file path."""
        assets_dir = Path(workspace_path) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        screenshot_paths = []
        VIEWPORT_HEIGHT = 1000
        VIEWPORT_WIDTH = 1200

        try:
            co = ChromiumOptions()
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(chrome_path):
                co.set_browser_path(chrome_path)
            
            if self.headless:
                co.headless()
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument(f'--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}')
            co.auto_port()
            
            page = ChromiumPage(co)
            page.get(f"file://{html_path.resolve()}")
            page.wait(2)
            
            total_height = page.run_js("return document.body.scrollHeight")
            
            # Use overlap to help VLM understand continuity
            OVERLAP = 200
            EFFECTIVE_HEIGHT = VIEWPORT_HEIGHT - OVERLAP
            num_screenshots = min(8, (total_height + EFFECTIVE_HEIGHT - 1) // EFFECTIVE_HEIGHT)
            
            if self.debug:
                print(f"    [VisualQA] Height: {total_height}px, Overlap: {OVERLAP}px, taking {num_screenshots} parts.")

            for i in range(num_screenshots):
                scroll_y = i * EFFECTIVE_HEIGHT
                page.run_js(f"window.scrollTo(0, {scroll_y})")
                
                # INJECT WATERMARK: Help VLM identify part and coordinates
                mark_js = f"""
                (function() {{
                    let old = document.getElementById('vqa-marker');
                    if (old) old.remove();
                    let div = document.createElement('div');
                    div.id = 'vqa-marker';
                    div.style.position = 'fixed';
                    div.style.top = '10px';
                    div.style.right = '10px';
                    div.style.background = 'rgba(255, 0, 0, 0.8)';
                    div.style.color = 'white';
                    div.style.padding = '5px 15px';
                    div.style.zIndex = '999999';
                    div.style.borderRadius = '20px';
                    div.style.fontFamily = 'monospace';
                    div.style.fontSize = '14px';
                    div.style.fontWeight = 'bold';
                    div.style.boxShadow = '0 2px 10px rgba(0,0,0,0.5)';
                    div.innerText = 'PART {i+1} | Scroll: {scroll_y}px';
                    document.body.appendChild(div);
                }})();
                """
                page.run_js(mark_js)
                page.wait(0.4)
                
                screen_path = assets_dir / f"vqa_{html_path.stem}_p{i+1}.jpg"
                page.get_screenshot(path=str(screen_path))
                
                # Compress for API safety
                try:
                     from PIL import Image
                     with Image.open(screen_path) as img:
                         img = img.convert('RGB')
                         img.save(screen_path, format="JPEG", quality=80, optimize=True)
                except: pass
                    
                screenshot_paths.append(screen_path)
            
            page.quit()
            return screenshot_paths
        except Exception as e:
            print(f"  [VisualQA] Screenshot failed for {html_path.name}: {e}")
            return []

    def _take_screenshots(self, state: AgentState) -> List[Path]:
        """Capture multiple viewport-sized screenshots by scrolling through the page."""
        html_path = Path(state.final_html_path).resolve()
        assets_dir = Path(state.workspace_path) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        iteration = getattr(state, 'vqa_iterations', 1)
        screenshot_paths = []
        
        VIEWPORT_HEIGHT = 1000  # Height of each screenshot
        VIEWPORT_WIDTH = 1200   # Width to simulate desktop view

        max_retries = 3
        for attempt in range(max_retries):
            try:
                co = ChromiumOptions()
                chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                if os.path.exists(chrome_path):
                    co.set_browser_path(chrome_path)
                
                if self.headless:
                    co.headless()
                co.set_argument('--no-sandbox')
                co.set_argument('--disable-gpu')
                co.set_argument('--disable-dev-shm-usage')
                co.set_argument(f'--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}')
                co.auto_port()
                
                page = ChromiumPage(co)
                page.get(f"file://{html_path}")
                
                # Wait for content and math/code rendering
                page.wait(3) 
                
                # Get total page height
                total_height = page.run_js("return document.body.scrollHeight")
                
                # Calculate number of screenshots needed
                num_screenshots = max(1, (total_height + VIEWPORT_HEIGHT - 1) // VIEWPORT_HEIGHT)
                num_screenshots = min(num_screenshots, 10)  # Cap at 10 screenshots
                
                if self.debug:
                    print(f"  [VisualQA] Page height: {total_height}px, taking {num_screenshots} screenshots")
                
                for i in range(num_screenshots):
                    scroll_y = i * VIEWPORT_HEIGHT
                    page.run_js(f"window.scrollTo(0, {scroll_y})")
                    page.wait(0.5)  # Wait for scroll to complete
                    
                    screenshot_path = assets_dir / f"visual_qa_v{iteration}_part{i+1}.png"
                    page.get_screenshot(path=str(screenshot_path), full_page=False)
                    screenshot_paths.append(screenshot_path)
                    
                    if self.debug:
                        print(f"  [VisualQA] Screenshot {i+1}/{num_screenshots} saved")
                
                page.quit()
                return screenshot_paths
                
            except Exception as e:
                print(f"  [VisualQA] Screenshot attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
        
        return []

    def _list_editable_files(self, state: AgentState) -> List[str]:
        """List files that the VLM is allowed to suggest fixes for."""
        files = []
        workspace = Path(state.workspace_path)
        
        # Sections
        for section in state.completed_html_sections:
            files.append(f"html/{Path(section).name}")
        
        # Assets
        if (workspace / "assets" / "style.css").exists():
            files.append("assets/style.css")
        if (workspace / "assets" / "main.js").exists():
            files.append("assets/main.js")
            
        return files

    def _get_vlm_critique(self, screenshot_paths: List[Path], html_code: str, file_list: List[str]) -> Optional[Dict]:
        """Send screenshots and data to VLM."""
        prompt = f"""# Editable Files in Workspace
{json.dumps(file_list, indent=2)}

# Complete HTML Source Code (with markers)
{html_code[:80000]}

I have provided {len(screenshot_paths)} screenshots showing different sections of the webpage (scrolled from top to bottom).
Please review ALL attached screenshots and provide comprehensive feedback on visual issues.
"""
        
        # Prepare parts for Gemini - include all screenshots
        parts = []
        import base64
        
        for i, screenshot_path in enumerate(screenshot_paths):
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
                parts.append({
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": image_data
                    }
                })
            parts.append({"text": f"[Screenshot {i+1}/{len(screenshot_paths)}]"})
        
        parts.append({"text": prompt})

        try:
            response = self.client.generate(
                parts=parts,
                system_instruction=VISUAL_QA_SYSTEM_PROMPT,
                temperature=0.0 # High precision
            )
            
            if not response.success:
                print(f"  [VisualQA] VLM Error: {response.error}")
                return None
            
            # Parse JSON from response
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            
            import re
            fixed_text = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)

            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                return json.loads(text)
        except Exception as e:
            print(f"  [VisualQA] Failed to parse VLM response: {e}")
            return None

    def _apply_fixes(self, state: AgentState, issues: List[Dict]) -> bool:
        """Apply the suggested fixes to the source files."""
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
                print(f"  [VisualQA] Warning: Suggested file {source_file_rel} not found.")
                continue
            
            content = source_file.read_text(encoding="utf-8")
            fix = issue.get("fix", {})
            fix_type = fix.get("type")
            
            if fix_type == "replace":
                target = fix.get("target")
                replacement = fix.get("replacement")
                
                if not target or target not in content:
                    print(f"  [VisualQA] Error: Target content not found in {source_file_rel}. Skipping.")
                    continue
                
                # Safety check: Ensure uniqueness
                count = content.count(target)
                if count > 1:
                    print(f"  [VisualQA] Error: Target content is ambiguous ({count} matches) in {source_file_rel}. VLM needs to provide more context. Skipping.")
                    continue
                    
                content = content.replace(target, replacement, 1)
                modified = True
                print(f"  [VisualQA] Replaced content in {source_file_rel}")
            
            elif fix_type == "append":
                new_content = fix.get("content")
                location = fix.get("location", "end")
                if new_content:
                    if location == "end":
                        content = content.rstrip() + "\n" + new_content + "\n"
                    else:
                        content = new_content + "\n" + content
                    modified = True
                    print(f"  [VisualQA] Appended content to {source_file_rel}")
            
            elif fix_type == "delete":
                target = fix.get("target")
                if target and target in content:
                    content = content.replace(target, "")
                    modified = True
                    print(f"  [VisualQA] Deleted content from {source_file_rel}")
            
            if modified:
                source_file.write_text(content, encoding="utf-8")
                
        return modified

    # ========== NEW DUAL-AGENT METHODS ==========
    
    def _run_critic(self, state: AgentState, section_path: str) -> Optional[Dict]:
        """Visual Critic: Analyze screenshots and return issue checklist (no code fixes)."""
        # Prepare test page and take screenshots
        test_html_path = self._prepare_section_test_page(state, section_path)
        if not test_html_path:
            return None
            
        screenshot_paths = self._take_screenshots_of_path(test_html_path, state.workspace_path)
        if not screenshot_paths:
            if test_html_path.exists(): test_html_path.unlink()
            return None
        
        # Load section code
        section_code = Path(section_path).read_text(encoding="utf-8")
        workspace = Path(state.workspace_path)
        
        css_code = ""
        if (workspace / "assets" / "style.css").exists():
            css_code = (workspace / "assets" / "style.css").read_text(encoding="utf-8")
        
        # Build prompt for Critic
        prompt = f"""# Visual Critique for: {Path(section_path).name}

## Section HTML (with line numbers)
```html
{self._add_line_numbers(section_code)}
```

## Global CSS
```css
{css_code[:3000]}
```

Analyze the attached {len(screenshot_paths)} screenshots and identify any visual issues.
"""
        
        # Build parts with images
        parts = []
        import base64
        import io
        from PIL import Image
        
        for i, path in enumerate(screenshot_paths):
            try:
                with Image.open(path) as img:
                    if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
                    if img.width > 1200:
                        ratio = 1200 / img.width
                        img = img.resize((1200, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=80, optimize=True)
                    image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image_data}})
                parts.append({"text": f"[Screenshot PART {i+1}]"})
            except Exception as e:
                print(f"    [Critic] Error loading image {path}: {e}")
        
        parts.append({"text": prompt})
        
        # Cleanup temp HTML
        if test_html_path.exists(): test_html_path.unlink()
        
        try:
            response = self.client.generate(
                parts=parts,
                system_instruction=CRITIC_SYSTEM_PROMPT,
                temperature=0.0
            )
            
            if self.debug:
                print(f"\n    [Critic Debug] Raw Response:\n{'-'*40}\n{response.text}\n{'-'*40}")
            
            if not response.success:
                print(f"    [Critic] API Error: {response.error}")
                return None
            
            return parse_json_dict_robust(response.text)
        except Exception as e:
            print(f"    [Critic] Exception: {e}")
            return None
    
    def _run_fixer(self, state: AgentState, section_path: str, issue: Dict) -> Optional[Dict]:
        """Code Fixer: Generate a fix for ONE specific issue."""
        workspace = Path(state.workspace_path)
        section_code = Path(section_path).read_text(encoding="utf-8")
        
        css_code = ""
        if (workspace / "assets" / "style.css").exists():
            css_code = (workspace / "assets" / "style.css").read_text(encoding="utf-8")
        
        js_code = ""
        if (workspace / "assets" / "main.js").exists():
            js_code = (workspace / "assets" / "main.js").read_text(encoding="utf-8")
        
        prompt = f"""# Issue to Fix

**ID**: {issue.get('id', 'unknown')}
**Severity**: {issue.get('severity', 'unknown')}
**Location**: {issue.get('location', 'unknown')}
**Element**: {issue.get('element', 'unknown')}
**Problem**: {issue.get('problem', 'No description')}

# Available Source Files

## html/{Path(section_path).name} (with line numbers)
```html
{self._add_line_numbers(section_code)}
```

## assets/style.css
```css
{self._add_line_numbers(css_code)}
```

## assets/main.js
```javascript
{self._add_line_numbers(js_code) if js_code else "(empty)"}
```

Generate a fix for the issue described above. Choose the most appropriate file to modify.
"""
        
        try:
            response = self.client.generate(
                prompt=prompt,
                system_instruction=FIXER_SYSTEM_PROMPT,
                temperature=0.0
            )
            
            if self.debug:
                print(f"\n    [Fixer Debug] Raw Response:\n{'-'*40}\n{response.text}\n{'-'*40}")
            
            if not response.success:
                print(f"    [Fixer] API Error: {response.error}")
                return None
            
            return parse_json_dict_robust(response.text)
        except Exception as e:
            print(f"    [Fixer] Exception: {e}")
            return None
    
    def _apply_single_fix(self, state: AgentState, fix_result: Dict) -> bool:
        """Apply a single fix from the Fixer agent."""
        workspace = Path(state.workspace_path)
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
    
    def _regenerate_section_preview(self, state: AgentState, section_path: str):
        """Regenerate the section preview HTML after fixes are applied."""
        # The next iteration will recreate the test page anyway
        # This is a placeholder for any additional re-rendering logic
        pass
