"""
CSSGeneratorAgent: Generates style.css based on Design Tokens.
Part of the decomposed Design phase for better separation of concerns.
"""

from pathlib import Path
from typing import Optional, Tuple
import json

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState, StyleMapping, StyleRule


CSS_GENERATOR_SYSTEM_PROMPT = """You are a **Senior CSS Architect** specializing in design systems and modern CSS.

## Your Task
Generate production-ready CSS based on Design Tokens and content requirements.

## Design Tokens Integration
You will receive a `design_tokens.json` specification. You MUST:
1. Convert ALL token values into CSS custom properties (variables) in `:root`
2. Reference these variables throughout your CSS (e.g., `var(--color-primary)`)
3. NEVER hardcode color, spacing, or typography values directly

## CSS Requirements

### 1. Structure
```css
/* 1. CSS Variables (from Design Tokens) */
:root {
  --color-primary: #...;
  --spacing-4: 1rem;
  /* etc. */
}

/* 2. Dark Mode Variables */
[data-theme="dark"] { ... }

/* 3. Reset & Base Styles */
/* 4. Typography */
/* 5. Layout Components */
/* 6. Content Components (cards, callouts, etc.) */
/* 7. Interactive Elements */
/* 8. Utilities */
/* 9. Print Styles */
/* 10. Responsive Breakpoints */
```

### 2. Modern CSS Features
- Use CSS Grid and Flexbox for layouts
- CSS custom properties for theming
- `clamp()` for fluid typography
- `aspect-ratio` for media
- Logical properties (`margin-inline`, `padding-block`)

### 3. Naming Convention
- Use BEM methodology: `.block__element--modifier`
- Semantic class names (e.g., `.article-card`, `.callout--warning`)

### 4. Accessibility
- Respect `prefers-reduced-motion`
- Ensure sufficient color contrast (WCAG AA)
- Focus styles for interactive elements

### 5. Performance
- Minimize specificity
- Avoid expensive selectors
- Use `will-change` sparingly

## Style Mapping Output
Also output a JSON mapping from Markdown patterns to CSS classes:
```json
{
  "important_card": "section.card.card--important",
  "warning_callout": "aside.callout.callout--warning",
  "formula_block": "div.math-block",
  "code_block": "pre.code-block"
}
```

## Output Format
1. Complete CSS code in ```css block
2. Style Mapping JSON in ```json block
"""


class CSSGeneratorAgent:
    """Agent that generates CSS based on Design Tokens."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        Generate style.css and style_mapping based on Design Tokens.
        
        Expects design_tokens to be populated in state.
        """
        if not state.manifest:
            state.errors.append("CSSGeneratorAgent: Manifest not available")
            return state
        
        # Get content preview
        full_content = self._get_content_preview(state)
        
        # Build prompt with Design Tokens
        design_tokens_section = self._format_design_tokens(state)
        
        prompt = f"""# Project Context
## SOTA Technical Specification
{state.manifest.description}

## Project Brief
{state.project_brief if state.project_brief else "N/A"}

## Global Project Config
{json.dumps(state.manifest.config, indent=2) if state.manifest.config else "{}"}

## Section Metadata (Layout/Design Intent)
{json.dumps([{"id": s.id, "metadata": s.metadata} for s in state.manifest.sections if s.metadata], indent=2)}

{design_tokens_section}

## Content Preview
{full_content[:6000]}

---

Generate a complete, production-ready CSS file based on the Design Tokens above.
Include both the CSS code and the Style Mapping JSON.
"""
        
        response = self.client.generate(
            prompt=prompt,
            system_instruction=CSS_GENERATOR_SYSTEM_PROMPT,
            temperature=0.4,
            stream=True  # 启用流式生成以避免 500 SSL 超时
        )
        
        if not response.success:
            state.errors.append(f"CSSGeneratorAgent API Error: {response.error}")
            return state
        
        # Parse response
        result = self._parse_response(response.text)
        if not result:
            state.errors.append("CSSGeneratorAgent: Failed to parse CSS response")
            return state
        
        css_code, style_mapping = result
        
        # Save CSS file
        try:
            state = self._save_css(state, css_code, style_mapping)
        except Exception as e:
            state.errors.append(f"CSSGeneratorAgent: Failed to save CSS: {e}")
        
        return state
    
    def _get_content_preview(self, state: AgentState) -> str:
        """Get preview of completed markdown sections."""
        parts = []
        for md_path in state.completed_md_sections:
            try:
                content = Path(md_path).read_text(encoding="utf-8")
                parts.append(content[:2000])
            except:
                pass
        return "\n\n---\n\n".join(parts)
    
    def _format_design_tokens(self, state: AgentState) -> str:
        """Format design tokens for the prompt."""
        if state.design_tokens and state.design_tokens.raw_json:
            return f"""## Design Tokens (MUST USE)
Convert these tokens into CSS variables and use them throughout your CSS.
```json
{json.dumps(state.design_tokens.raw_json, indent=2, ensure_ascii=False)}
```
"""
        else:
            return """## Design Tokens
No design tokens available. Generate a comprehensive set of CSS variables based on the project requirements.
"""
    
    def _parse_response(self, text: str) -> Optional[Tuple[str, StyleMapping]]:
        """Parse CSS and Style Mapping from response."""
        css_code = self._extract_code_block(text, "css")
        json_text = self._extract_code_block(text, "json")
        
        if not css_code:
            return None
        
        # Parse Style Mapping
        style_mapping = StyleMapping(rules=[])
        if json_text:
            try:
                data = json.loads(json_text)
                for key, value in data.items():
                    if isinstance(value, dict):
                        if "class" in value:
                            value_str = value["class"]
                        else:
                            value_str = " ".join([f"{v}" for v in value.values() if isinstance(v, str)])
                    else:
                        value_str = str(value)
                    
                    style_mapping.rules.append(StyleRule(
                        markdown_pattern=key,
                        css_selector=value_str,
                    ))
            except json.JSONDecodeError:
                pass
        
        return css_code, style_mapping
    
    def _extract_code_block(self, text: str, language: str) -> Optional[str]:
        """Extract code block from response."""
        import re
        pattern = rf"```{language}\s*(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None
    
    def _save_css(self, state: AgentState, css_code: str, style_mapping: StyleMapping) -> AgentState:
        """Save CSS file and style mapping."""
        assets_dir = Path(state.workspace_path) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Save CSS
        css_path = assets_dir / "style.css"
        css_path.write_text(css_code, encoding="utf-8")
        state.css_path = str(css_path)
        
        # Save Style Mapping
        mapping_path = Path(state.workspace_path) / "style_mapping.json"
        mapping_path.write_text(
            style_mapping.model_dump_json(indent=2),
            encoding="utf-8"
        )
        state.style_mapping = style_mapping
        
        print(f"  [CSSGenerator] Saved style.css ({len(css_code)} bytes)")
        print(f"  [CSSGenerator] Saved style_mapping.json ({len(style_mapping.rules)} rules)")
        
        return state


def create_css_generator_agent(client: Optional[GeminiClient] = None) -> CSSGeneratorAgent:
    """Create CSSGeneratorAgent instance."""
    return CSSGeneratorAgent(client=client)
