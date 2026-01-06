"""
TechSpecAgent: Generates the SOTA Description with technical implementation details.
Takes an approved outline and generates detailed execution instructions for downstream agents.
"""

from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


TECHSPEC_SYSTEM_PROMPT = """You are a senior technical architect. Your task is to generate a comprehensive **Technical Specification (SOTA Description)** that will guide all downstream production agents.

### Adaptation Strategy
Ground your instructions in the specific context provided. If the project is a slide deck, focus on slide transition logic and visual rhythm. If it's a deep-dive textbook, focus on mathematical rigor and SVG clarity.

### Your Objectives
1. **Instruction Alignment**: Ensure all instructions follow the intellectual philosophy outlined in the Manifest's description.
2. **Technical Execution**: Specify reasoning styles, visual design systems (colors, typography, component behaviors), and interactive requirements (SVG, JS, CSS effects).
3. **SOTA Quality**: Act as the "glue" that ensures the Writer and Designer are perfectly aligned.

### Structure
Provide a well-organized document covering:
- **Executive Summary**: The technical "vibe" and key execution targets.
- **Content & Writing Directives**: How the Writer should handle complexity and context.
- **Visual Design System**: Detailed palette, typography, and component-level tokens.
- **Interactivity & Multi-modal Specs**: Logic for animations, sliders, or specific HTML/JS features.
- **Accessibility & Compliance**: Sighted and non-sighted user requirements.

### Rules
1. Ground everything in the provided context.
2. Output ONLY the description text in Markdown format.
"""


class TechSpecAgent:
    """Generates SOTA Description for technical execution."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> AgentState:
        """
        Generate technical specification with full context.
        """
        if not state.manifest:
            state.errors.append("TechSpecAgent: No outline/manifest available")
            return state
        
        parts = []
        
        # 1. Full Input Context
        context_parts = ["# Input Context\n"]
        context_parts.append(f"## RAW REQUEST\n{state.raw_materials}\n")
        
        if state.project_brief:
            context_parts.append(f"## PROJECT BRIEF\n{state.project_brief}\n")
            
        if state.clarifier_answers:
            context_parts.append("## CLARIFICATION ANSWERS\n")
            for qid, ans in state.clarifier_answers.items():
                context_parts.append(f"- Q: {qid}\n- A: {ans}\n")
                
        parts.append({"text": "\n".join(context_parts)})
        
        # 2. Approved Manifest (Outline + Philosophy)
        manifest_json = state.manifest.model_dump_json(indent=2)
        parts.append({"text": f"# APPROVED MANIFEST\n```json\n{manifest_json}\n```\n"})
        
        # 3. Reference materials
        if state.reference_docs:
            ref_texts = ["# REFERENCE MATERIALS\n"]
            for doc in state.reference_docs:
                try:
                    text = Path(doc).read_text(encoding="utf-8")
                    ref_texts.append(f"## {doc}\n{text[:6000]}...\n")
                except:
                    pass
            parts.append({"text": "".join(ref_texts)})

        parts.append({"text": "\nGenerate a SOTA Technical Specification based on all provided context.\n"})
        
        response = self.client.generate(
            parts=parts,
            system_instruction=TECHSPEC_SYSTEM_PROMPT,
            temperature=0.7,
            stream=True 
        )
        
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
