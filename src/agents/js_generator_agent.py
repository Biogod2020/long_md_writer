"""
JSGeneratorAgent: Generates main.js for interactive features.
Part of the decomposed Design phase for better separation of concerns.
"""

import json
from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


JS_GENERATOR_SYSTEM_PROMPT = """You are a **Senior JavaScript Engineer** specializing in vanilla JavaScript for interactive documents.

## Your Task
Generate production-ready JavaScript for a technical document's interactive features.

## Core Features to Implement

### 1. Table of Contents (TOC)
- Auto-generate from headings (h2, h3)
- Scroll spy to highlight current section
- Smooth scroll on click
- Collapsible for mobile

### 2. Theme Toggle (Dark/Light Mode)
- Toggle button with icon swap
- Persist preference in localStorage
- Respect `prefers-color-scheme`
- Smooth transition between themes

### 3. Reading Progress
- Progress bar at top of page
- Section-level progress indicators
- Reading time estimate

### 4. Code Block Utilities
- Copy to clipboard button
- Syntax highlighting integration (if Prism/Highlight.js)
- Language label display

### 5. Math Rendering
- Initialize MathJax or KaTeX
- Handle inline and block equations
- Re-render on dynamic content

### 6. Image Handling
- Lazy loading
- Lightbox/zoom on click
- Fallback for broken images

### 7. Interactive Elements
- Collapsible sections (details/summary enhancement)
- Tabs component
- Accordion component

## JavaScript Requirements

### 1. Code Structure
```javascript
// 1. Configuration
const CONFIG = { ... };

// 2. DOM Utilities
const DOM = { ... };

// 3. Feature Modules
const TOC = { init() { ... } };
const Theme = { init() { ... } };
const Progress = { init() { ... } };
// etc.

// 4. Main Initialization
document.addEventListener('DOMContentLoaded', () => {
  TOC.init();
  Theme.init();
  Progress.init();
  // etc.
});
```

### 2. Best Practices
- Use ES6+ syntax (const, let, arrow functions, template literals)
- Event delegation where appropriate
- Debounce/throttle scroll handlers
- Graceful degradation (check for feature support)
- No jQuery or heavy frameworks

### 3. Performance
- Defer non-critical operations
- Use IntersectionObserver for lazy loading
- Minimize DOM queries (cache references)
- requestAnimationFrame for animations

### 4. Accessibility
- Keyboard navigation support
- ARIA attributes for dynamic content
- Focus management for modals/overlays

### 5. Integration Points
The following IDs/selectors MUST be supported:
- `#theme-toggle` - Theme switch button
- `#toc-container` or `.toc` - Table of contents container
- `#progress-bar` - Reading progress bar
- `.code-block` - Code blocks for copy functionality
- `.math-block`, `.math-inline` - Math containers

## Output Format
Output the complete JavaScript code in a ```javascript block.
"""


class JSGeneratorAgent:
    """Agent that generates main.js for interactive features."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        Generate main.js based on project requirements.
        
        Independent of CSS generation - can run in parallel.
        """
        if not state.manifest:
            state.errors.append("JSGeneratorAgent: Manifest not available")
            return state
        
        # Get content preview
        full_content = self._get_content_preview(state)
        
        # Build prompt
        prompt = f"""# Project Context

## SOTA Technical Specification
{state.manifest.description}

## Document Structure
Sections: {[s.title for s in state.manifest.sections]}

## Global Project Config
{json.dumps(state.manifest.config, indent=2) if state.manifest.config else "{}"}

## Section Metadata (Interactivity/Widgets)
{json.dumps([{"id": s.id, "metadata": s.metadata} for s in state.manifest.sections if s.metadata], indent=2)}

## Content Preview
{full_content}

---

Generate a complete, production-ready JavaScript file for this technical document.
Include all core interactive features and follow the module pattern.
"""
        
        response = self.client.generate(
            prompt=prompt,
            system_instruction=JS_GENERATOR_SYSTEM_PROMPT,
            temperature=0.4,
            stream=True  # 启用流式生成以避免 500 SSL 超时
        )
        
        if not response.success:
            state.errors.append(f"JSGeneratorAgent API Error: {response.error}")
            return state
        
        # Extract JavaScript code
        js_code = self._extract_js(response.text)
        if not js_code:
            state.errors.append("JSGeneratorAgent: Failed to extract JavaScript")
            return state
        
        # Save JS file
        try:
            state = self._save_js(state, js_code)
        except Exception as e:
            state.errors.append(f"JSGeneratorAgent: Failed to save JS: {e}")
        
        return state
    
    def _get_content_preview(self, state: AgentState) -> str:
        """Get preview of completed markdown sections."""
        parts = []
        for md_path in state.completed_md_sections:  # All sections - no limit
            try:
                content = Path(md_path).read_text(encoding="utf-8")
                parts.append(content)  # Full content - no truncation
            except:
                pass
        return "\n\n---\n\n".join(parts)
    
    def _extract_js(self, text: str) -> Optional[str]:
        """Extract JavaScript code from response."""
        import re
        
        # Try javascript block first
        pattern = r"```javascript\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try js block
        pattern = r"```js\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _save_js(self, state: AgentState, js_code: str) -> AgentState:
        """Save JavaScript file."""
        assets_dir = Path(state.workspace_path) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        js_path = assets_dir / "main.js"
        js_path.write_text(js_code, encoding="utf-8")
        state.js_path = str(js_path)
        
        print(f"  [JSGenerator] Saved main.js ({len(js_code)} bytes)")
        
        return state


def create_js_generator_agent(client: Optional[GeminiClient] = None) -> JSGeneratorAgent:
    """Create JSGeneratorAgent instance."""
    return JSGeneratorAgent(client=client)
