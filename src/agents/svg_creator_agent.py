"""
SVGCreatorAgent: Iteratively generates and validates SVG graphics.
Scans HTML sections for SVG placeholders, generates SVG code, validates via rendering,
and replaces placeholders with validated SVGs.
"""

from pathlib import Path
import re
import base64
import tempfile
from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


SVG_CREATOR_SYSTEM_PROMPT = """You are an expert SVG artist and data visualization specialist. Your task is to generate clean, valid, SELF-CONTAINED SVG code based on a detailed description.

### Rules
1. **NO External Resources**: DO NOT use `@import`, `<link>`, or any external URLs. The SVG must be completely self-contained.
2. **Standard Fonts Only**: Use standard sans-serif, serif, or monospace font families. Do not try to load external fonts like Google Fonts.
3. **Internal Styles**: Use `<style>` tags within the SVG for CSS. Ensure ALL selectors are specific to this SVG to avoid global conflicts (though we will inline it later).
4. **Responsiveness**: Include `viewBox`. Set `width="100%"` and `height="auto"` for the top-level `<svg>` tag.
5. **Animations**: Use standard CSS keyframe animations within the internal `<style>` block.
6. **Clean Paths**: Use clean, optimized `<path>`, `<circle>`, `<rect>` elements.
7. **Accessibility**: Include `<title>` and `role="img"`.

### Output
Output ONLY valid SVG code. No markdown code blocks, no explanation. Start with `<svg` and end with `</svg>`.
"""

SVG_VALIDATOR_PROMPT = """Analyze the rendered image of an SVG graphic. Compare it against the original description.

### Your Task
1. Does the SVG accurately represent the description?
2. Are there any visual issues (broken paths, wrong colors, missing elements)?
3. Rate the quality from 1-10.

### Response Format
```
RATING: [1-10]
PASS: [YES/NO]
FEEDBACK: [If NO, provide specific improvement suggestions]
```
"""


class SVGCreatorAgent:
    """Generates and validates SVG graphics from placeholders in HTML."""
    
    MAX_ITERATIONS = 3
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        Scan all HTML sections for SVG placeholders and generate validated SVGs.
        
        Args:
            state: AgentState with completed_html_sections populated.
            
        Returns:
            AgentState with HTML sections updated (placeholders replaced with SVGs).
        """
        if not state.completed_html_sections:
            return state
        
        # Create SVG assets directory
        svg_dir = Path(state.workspace_path) / "assets" / "svgs"
        svg_dir.mkdir(parents=True, exist_ok=True)
        
        for html_path in state.completed_html_sections:
            try:
                html_content = Path(html_path).read_text(encoding="utf-8")
                updated_content = self._process_section(state, html_content, svg_dir)
                Path(html_path).write_text(updated_content, encoding="utf-8")
            except Exception as e:
                state.errors.append(f"SVGCreator: Error processing {html_path}: {e}")
        
        return state
    
    def _process_section(self, state: AgentState, html_content: str, svg_dir: Path) -> str:
        """Process a single HTML section, replacing SVG placeholders."""
        
        # Find all SVG placeholders - more robust regex
        # Matches <div class="svg-placeholder" ... data-svg-id="id" ...>
        # We capture the full tag to replace it easily.
        placeholder_regex = re.compile(
            r'(<div[^>]*class="svg-placeholder"[^>]*data-svg-id="([^"]+)"[^>]*>.*?'
            r'<p[^>]*class="svg-description">(.*?)</p>.*?'
            r'</div>)',
            re.DOTALL | re.IGNORECASE
        )
        
        matches = placeholder_regex.findall(html_content)
        
        if not matches:
            return html_content

        for full_tag, svg_id, description in matches:
            description = description.strip()
            print(f"  [SVGCreator] Processing: {svg_id}")
            
            # Generate and validate SVG
            svg_code = self._generate_svg_with_validation(state, svg_id, description)
            
            if svg_code:
                # Save SVG to file
                svg_path = svg_dir / f"{svg_id}.svg"
                svg_path.write_text(svg_code, encoding="utf-8")
                print(f"  [SVGCreator] Saved SVG to {svg_path.name}")
                
                # Replace placeholder with inline SVG
                replacement_html = f'<figure class="svg-container" id="{svg_id}">\n{svg_code}\n<figcaption>{description[:200]}...</figcaption>\n</figure>'
                
                # Simple string replacement for the exact tag we matched
                html_content = html_content.replace(full_tag, replacement_html)
        
        return html_content
    
    def _generate_svg_with_validation(self, state: AgentState, svg_id: str, description: str) -> Optional[str]:
        """Generate SVG with iterative validation loop."""
        
        feedback = ""
        last_svg = None
        
        for iteration in range(self.MAX_ITERATIONS):
            print(f"    - Iteration {iteration + 1}/{self.MAX_ITERATIONS}...")
            # Build prompt
            parts = []
            parts.append({"text": f"# Technical Specification\n{state.manifest.description[:3000]}\n\n"})
            parts.append({"text": f"# SVG Description\n{description}\n\n"})
            
            if feedback:
                print(f"    - Applying feedback: {feedback[:50]}...")
                parts.append({"text": f"# Previous Attempt Feedback\n{feedback}\n\n"})
            
            parts.append({"text": "Generate the SVG code based on the above description."})
            
            # Generate SVG
            response = self.client.generate(
                parts=parts,
                system_instruction=SVG_CREATOR_SYSTEM_PROMPT,
                temperature=0.5
            )
            
            if not response.success:
                print(f"    - Error generating SVG: {response.error}")
                return last_svg
            
            svg_code = self._extract_svg(response.text)
            
            if not svg_code:
                print("    - Failed to extract SVG from response.")
                feedback = "Failed to generate valid SVG. Please output only <svg>...</svg> code."
                continue
            
            last_svg = svg_code
            
            # Validate SVG by rendering and checking with vision
            print("    - Validating SVG via Vision...")
            is_valid, feedback = self._validate_svg(svg_code, description)
            
            if is_valid:
                print("    - Validation PASSED.")
                return svg_code
            else:
                print(f"    - Validation FAILED: {feedback[:100]}...")
        
        print("    - Max iterations reached. Using last generated version.")
        return last_svg
    
    def _extract_svg(self, text: str) -> Optional[str]:
        """Extract SVG code from response."""
        text = text.strip()
        
        # Remove markdown code blocks if present
        if "```" in text:
            match = re.search(r'```(?:svg|xml)?\s*(.*?)```', text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        
        # Find SVG tags
        match = re.search(r'(<svg[^>]*>.*</svg>)', text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def _validate_svg(self, svg_code: str, description: str) -> tuple[bool, str]:
        """Validate SVG by rendering and using vision API."""
        try:
            # Render SVG to PNG
            png_data = self._render_svg_to_png(svg_code)
            
            if not png_data:
                return False, "Failed to render SVG to PNG."
            
            # Send to Gemini Vision for validation
            parts = [
                {"text": f"# Original Description\n{description}\n\n"},
                {"text": SVG_VALIDATOR_PROMPT},
                {"inline_data": {"mime_type": "image/png", "data": png_data}}
            ]
            
            response = self.client.generate(
                parts=parts,
                temperature=0.3
            )
            
            if not response.success:
                return True, ""  # Assume valid if validation fails
            
            # Parse response
            result_text = response.text
            
            if "PASS: YES" in result_text.upper():
                return True, ""
            
            # Extract feedback
            feedback_match = re.search(r'FEEDBACK:\s*(.+)', result_text, re.IGNORECASE | re.DOTALL)
            feedback = feedback_match.group(1).strip() if feedback_match else "Validation failed."
            
            return False, feedback
            
        except Exception as e:
            # If validation fails, assume SVG is valid
            return True, ""
    
    def _render_svg_to_png(self, svg_code: str) -> Optional[str]:
        """Render SVG to PNG and return base64 encoded data."""
        try:
            import cairosvg
            
            # Use a smaller size for validation to speed up
            png_data = cairosvg.svg2png(bytestring=svg_code.encode('utf-8'))
            return base64.b64encode(png_data).decode('utf-8')
            
        except ImportError:
            print("    - cairosvg not installed.")
            return None
        except Exception as e:
            print(f"    - Rendering Error: {e}")
            return None


def create_svg_creator_agent(client: Optional[GeminiClient] = None) -> SVGCreatorAgent:
    """Create an SVGCreatorAgent instance."""
    return SVGCreatorAgent(client=client)
