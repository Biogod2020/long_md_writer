"""
TechSpecAgent: Generates the SOTA Description with technical implementation details.
Takes an approved outline and generates detailed execution instructions for downstream agents.
"""

from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


TECHSPEC_SYSTEM_PROMPT = """You are a senior technical architect. Your task is to generate a comprehensive **Technical Specification (SOTA Description)** that will guide all downstream agents (Writer, Designer, Transformer).

### Your Role
Based on the project context and approved outline, specify:
1. **Content Deep-Dive Requirements** for the Writer.
2. **Visual Design Guidelines** for the Designer.
3. **Interactive Element Specifications** for the Transformer.

### Output Structure
Generate a detailed description (300-500 words) covering:

#### 1. Content Guidelines
- Preferred reasoning style (first-principles, inductive, deductive, example-driven)
- Level of mathematical/technical rigor required
- Citation and evidence requirements

#### 2. Visual Design System
- Color palette suggestions (dark/light mode, accent colors)
- Typography recommendations
- Component styles (cards, callouts, code blocks)

#### 3. Interactive Elements (if applicable)
- SVG animation requirements (what should be animated and why)
- CSS effects (glassmorphism, gradients, transitions)
- JavaScript interactions (sliders, toggles, progressive disclosure)

#### 4. Accessibility & Performance
- Accessibility requirements (alt text, contrast, keyboard navigation)
- Performance considerations

### Rules
1. Be SPECIFIC. Generic descriptions are useless.
2. Ground everything in the Project Brief and Outline context.
3. Output ONLY the description text in Markdown format, NOT JSON.
"""


class TechSpecAgent:
    """Generates SOTA Description for technical execution."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        Generate technical specification based on Project Brief and Outline.
        
        Args:
            state: AgentState with project_brief and manifest (outline) populated.
            
        Returns:
            AgentState with manifest.description populated.
        """
        if not state.manifest:
            state.errors.append("TechSpecAgent: No outline/manifest available")
            return state
        
        parts = []
        
        # 1. Project Brief
        if state.project_brief:
            parts.append({"text": "# Project Brief\n" + state.project_brief + "\n\n"})
        
        # 2. Raw Materials (additional context)
        if state.raw_materials:
            parts.append({"text": "# Original Source Materials (for reference)\n" + state.raw_materials[:8000] + "\n\n"})
        
        # 3. Approved Outline
        outline_summary = ["# Approved Outline\n"]
        outline_summary.append(f"**Title**: {state.manifest.project_title}\n\n")
        outline_summary.append("**Sections**:\n")
        for sec in state.manifest.sections:
            outline_summary.append(f"- **{sec.id}**: {sec.title}\n  {sec.summary[:100]}...\n")
        parts.append({"text": "".join(outline_summary) + "\n"})
        
        parts.append({"text": "Based on the above Project Brief, source materials, and approved outline, generate a comprehensive Technical Specification (SOTA Description).\n"})
        
        response = self.client.generate(
            parts=parts,
            system_instruction=TECHSPEC_SYSTEM_PROMPT,
            temperature=0.7
        )
        
        # Debug: save response
        try:
            log_path = Path(state.workspace_path) / "techspec_raw_response.txt"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(response.text, encoding="utf-8")
        except:
            pass
        
        if not response.success:
            state.errors.append(f"TechSpecAgent failed: {response.error}")
            return state
        
        # Update manifest description
        state.manifest.description = response.text
        self._save_manifest(state)
        
        return state
    
    def _save_manifest(self, state: AgentState) -> None:
        """Save complete manifest to workspace."""
        if not state.manifest:
            return
        manifest_path = Path(state.workspace_path) / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            state.manifest.model_dump_json(indent=2),
            encoding="utf-8"
        )


def create_techspec_agent(client: Optional[GeminiClient] = None) -> TechSpecAgent:
    """Create a TechSpecAgent instance."""
    return TechSpecAgent(client=client)
