"""
DesignTokensAgent: Generates design_tokens.json before CSS/JS generation.
This follows SOTA practices where tokens are the single source of truth.
"""

from pathlib import Path
from typing import Optional
import json

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState, DesignTokens


DESIGN_TOKENS_SYSTEM_PROMPT = """You are a **Design Systems Architect** specializing in design tokens. 
Your task is to create a comprehensive, platform-agnostic design token specification that will serve as the single source of truth for all visual decisions.

## Design Tokens Philosophy
Design tokens are named entities that store visual design decisions. They enable:
1. **Consistency**: All components reference the same values
2. **Scalability**: Easy theming and multi-platform support
3. **Maintainability**: Change one token, update everywhere

## Token Categories to Define

### 1. Color Tokens (Primitive + Semantic)
```json
"colors": {
  "primitive": {
    "blue-50": "#eff6ff",
    "blue-500": "#3b82f6",
    "gray-900": "#111827"
  },
  "semantic": {
    "background-primary": "{colors.primitive.gray-900}",
    "text-primary": "{colors.primitive.gray-50}",
    "accent": "{colors.primitive.blue-500}",
    "border-default": "rgba(255,255,255,0.1)"
  }
}
```

### 2. Typography Tokens
```json
"typography": {
  "font-family": {
    "heading": "'Inter', sans-serif",
    "body": "'Inter', sans-serif", 
    "mono": "'JetBrains Mono', monospace"
  },
  "font-size": {
    "xs": "0.75rem",
    "sm": "0.875rem",
    "base": "1rem",
    "lg": "1.125rem",
    "xl": "1.25rem",
    "2xl": "1.5rem",
    "3xl": "1.875rem",
    "4xl": "2.25rem"
  },
  "line-height": {
    "tight": "1.25",
    "normal": "1.5",
    "relaxed": "1.75"
  },
  "font-weight": {
    "normal": "400",
    "medium": "500",
    "semibold": "600",
    "bold": "700"
  }
}
```

### 3. Spacing Tokens
```json
"spacing": {
  "0": "0",
  "1": "0.25rem",
  "2": "0.5rem",
  "3": "0.75rem",
  "4": "1rem",
  "6": "1.5rem",
  "8": "2rem",
  "12": "3rem",
  "16": "4rem"
}
```

### 4. Effects Tokens
```json
"effects": {
  "shadow": {
    "sm": "0 1px 2px rgba(0,0,0,0.05)",
    "md": "0 4px 6px rgba(0,0,0,0.1)",
    "lg": "0 10px 15px rgba(0,0,0,0.1)"
  },
  "border-radius": {
    "sm": "0.125rem",
    "md": "0.375rem",
    "lg": "0.5rem",
    "xl": "0.75rem",
    "full": "9999px"
  },
  "blur": {
    "sm": "4px",
    "md": "8px",
    "lg": "16px"
  }
}
```

### 5. Component Tokens (Semantic Mappings)
```json
"components": {
  "card": {
    "background": "{colors.semantic.background-secondary}",
    "border": "{colors.semantic.border-default}",
    "border-radius": "{effects.border-radius.lg}",
    "padding": "{spacing.6}"
  },
  "button-primary": {
    "background": "{colors.semantic.accent}",
    "text": "{colors.primitive.white}",
    "border-radius": "{effects.border-radius.md}"
  },
  "callout-warning": {
    "background": "rgba(245, 158, 11, 0.1)",
    "border-color": "#f59e0b",
    "text": "{colors.semantic.text-primary}"
  }
}
```

## Output Format
Return a complete JSON object with all token categories.
Ensure tokens are linked to the document's tone, audience, and technical requirements from the brief.

For SOTA technical documents, prefer:
- Dark mode as default (easier on eyes for long reading)
- Generous spacing for readability
- Clear visual hierarchy through typography scale
- Clean, modern professional effects
- Accent colors that match the subject matter
"""


class DesignTokensAgent:
    """Agent that generates design tokens as single source of truth."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        Generate design tokens based on project brief and content analysis.
        
        This should run BEFORE CSS and JS generation.
        """
        if not state.manifest:
            state.errors.append("DesignTokensAgent: Manifest not available")
            return state
        
        # Get content preview for context
        content_preview = self._get_content_preview(state)
        
        # 注入用户意图上下文 (Context Chain)
        user_ctx = state.user_context if state.user_context else ""
        
        prompt = f"""# 用户意图上下文 (Context Chain)
{user_ctx}

---

# Global Project Config
{json.dumps(state.manifest.config, indent=2) if state.manifest.config else "{}"}

# SOTA Technical Specification
{state.manifest.description}

# Document Structure
Sections: {[s.title for s in state.manifest.sections]}

# Content Preview
{content_preview}

---

Based on the above user context and project specification, generate a comprehensive design token specification.
Consider:
1. The user's stated visual preferences from clarification Q&A.
2. The global config preferences (e.g., if theme is "light", prioritize light primitive colors).
3. The document's subject matter (choose appropriate accent colors).
4. The target audience (academic, professional, casual).
5. Accessibility standards (WCAG contrast ratios).

Output a complete JSON object with all design tokens.
"""
        
        # Check for Structured Output capability
        if hasattr(self.client, "generate_structured"):
            try:
                print("    [DesignTokens] Using Structured Output (JSON Schema)...")
                schema = DesignTokens.model_json_schema()
                
                response = self.client.generate_structured(
                    prompt=prompt,
                    response_schema=schema,
                    schema_name="DesignTokens",
                    system_instruction=DESIGN_TOKENS_SYSTEM_PROMPT,
                    temperature=0.6
                )
                
                if response.success and response.json_data:
                    # Initialize DesignTokens with the data
                    # We might need to handle 'raw_json' field which we use to store the full dict
                    data = response.json_data
                    tokens = DesignTokens(
                        colors=data.get("colors", {}),
                        typography=data.get("typography", {}),
                        spacing=data.get("spacing", {}),
                        effects=data.get("effects", {}),
                        components=data.get("components", {}),
                        raw_json=data
                    )
                    state.design_tokens = tokens
                    self._save_tokens(state, tokens)
                    return state
                else:
                     print(f"    [DesignTokens] Structured generation failed: {response.error}. Falling back...")
            except Exception as e:
                print(f"    [DesignTokens] Structured generation error: {e}. Falling back...")

        response = self.client.generate(
            prompt=prompt,
            system_instruction=DESIGN_TOKENS_SYSTEM_PROMPT,
            temperature=0.6,
            stream=True  # 启用流式生成以避免 500 SSL 超时
        )
        
        if not response.success:
            state.errors.append(f"DesignTokensAgent API Error: {response.error}")
            return state
        
        # Parse and save design tokens
        try:
            tokens = self._parse_tokens(response.text)
            state.design_tokens = tokens
            self._save_tokens(state, tokens)
        except Exception as e:
            state.errors.append(f"DesignTokensAgent: Failed to parse tokens: {e}")
            # Save raw response for debugging
            try:
                debug_path = Path(state.workspace_path) / "design_tokens_raw.txt"
                debug_path.write_text(response.text, encoding="utf-8")
            except:
                pass
        
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
    
    def _parse_tokens(self, text: str) -> DesignTokens:
        """Parse design tokens JSON from LLM response."""
        import re
        
        cleaned = text.strip()
        
        # Extract JSON from markdown code block if present
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            # Find JSON object directly
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
        
        data = json.loads(cleaned)
        
        return DesignTokens(
            colors=data.get("colors", {}),
            typography=data.get("typography", {}),
            spacing=data.get("spacing", {}),
            effects=data.get("effects", {}),
            components=data.get("components", {}),
            raw_json=data
        )
    
    def _save_tokens(self, state: AgentState, tokens: DesignTokens) -> None:
        """Save design tokens to workspace."""
        tokens_path = Path(state.workspace_path) / "design_tokens.json"
        tokens_path.parent.mkdir(parents=True, exist_ok=True)
        tokens_path.write_text(
            json.dumps(tokens.raw_json, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


def create_design_tokens_agent(client: Optional[GeminiClient] = None) -> DesignTokensAgent:
    """Create DesignTokensAgent instance."""
    return DesignTokensAgent(client=client)
