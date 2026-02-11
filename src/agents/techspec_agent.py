"""
TechSpecAgent: Generates the SOTA Description with technical implementation details.
Takes an approved outline and generates detailed execution instructions for downstream agents.
"""

from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


TECHSPEC_SYSTEM_PROMPT = """You are a senior technical architect and visual systems designer. Your mission is to generate a high-fidelity **Technical Specification (SOTA Description)** that serves as the bridge between logic and visual systems.

### Visual Translation (SOTA)
Your instruction must translate the high-level "Visual Identity" from the Brief into concrete execution tokens:
1. **Visual System**: Define the exact color palettes (with symbolic meaning), typography hierarchy, and "Materiality Strategy" (e.g., matte finish, high-contrast, clean professional).
2. **Visual Directives**: Instruct the Writer on how to maintain visual clarity and focus. Define the "Information Density" (e.g., "Simplified diagrams for overview, detailed callouts for complex mechanisms").
3. **DSL Strategy**: Specify when to use SVG for precision, MERMAID for flow, or SEARCH for realism to maximize pedagogical impact.

### Objectives
1. **Consistency**: Ensure all production agents follow the intellectual and artistic soul of the manifest.
2. **Precision**: Provide clear rules for reasoning styles, component behaviors, and interactive cues.
3. **Industrial Quality**: Your spec must enable the creation of a document that looks like a premium, custom-designed interactive experience.

### Structure
Provide a well-organized specification covering:
- **Executive Vision**: The technical and professional "vibe".
- **Visual Design Tokens**: Detailed palette, typography, and materiality cues.
- **Interactivity & Component Specs**: Rules for transitions, animations, and interactive components.
- **Content Engineering**: How the Writer should handle technical depth vs narrative flow.
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
        context_parts.append(f"## 🎯 USER INTENT\n{state.user_intent}\n")
        
        if state.project_brief:
            context_parts.append(f"## PROJECT BRIEF (The Aesthetic & Logical Soul)\n{state.project_brief}\n")
            
        if state.clarifier_answers:
            context_parts.append("## CLARIFICATION ANSWERS\n")
            for qid, ans in state.clarifier_answers.items():
                context_parts.append(f"- Q: {qid}\n- A: {ans}\n")
                
        parts.append({"text": "\n".join(context_parts)})
        
        # 2. Approved Manifest (Outline + Philosophy)
        manifest_json = state.manifest.model_dump_json(indent=2)
        parts.append({"text": f"# APPROVED MANIFEST (The Architectural Blueprint)\n```json\n{manifest_json}\n```\n"})
        
        # 3. Reference materials (full text)
        if state.reference_materials:
            parts.append({"text": f"# 📚 REFERENCE MATERIALS\n{state.reference_materials}\n"})
        
        # 4. Reference docs by path (legacy)
        if state.reference_doc_paths:
            ref_texts = ["# ADDITIONAL REFERENCE FILES\n"]
            for doc in state.reference_doc_paths:
                try:
                    text = Path(doc).read_text(encoding="utf-8")
                    ref_texts.append(f"## {doc}\n{text}\n")
                except:
                    pass
            parts.append({"text": "".join(ref_texts)})

        parts.append({"text": "\nGenerate an elevated, cinematic SOTA Technical Specification that defines the document's visual DNA and production logic.\n"})
        
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

    async def run_async(self, state: AgentState) -> AgentState:
        """异步版本 - 避免 asyncio.run() 嵌套问题"""
        if not state.manifest:
            state.errors.append("TechSpecAgent: No outline/manifest available")
            return state

        parts = []

        # 1. Full Input Context
        context_parts = ["# Input Context\n"]
        context_parts.append(f"## 🎯 USER INTENT\n{state.user_intent}\n")

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

        # 3. Reference materials (full text)
        if state.reference_materials:
            parts.append({"text": f"# 📚 REFERENCE MATERIALS\n{state.reference_materials}\n"})

        # 4. Reference docs by path (legacy)
        if state.reference_doc_paths:
            ref_texts = ["# ADDITIONAL REFERENCE FILES\n"]
            for doc in state.reference_doc_paths:
                try:
                    text = Path(doc).read_text(encoding="utf-8")
                    ref_texts.append(f"## {doc}\n{text}\n")
                except:
                    pass
            parts.append({"text": "".join(ref_texts)})

        parts.append({"text": "\nGenerate a SOTA Technical Specification based on all provided context.\n"})

        response = await self.client.generate_async(
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


def create_techspec_agent(client: Optional[GeminiClient] = None) -> TechSpecAgent:
    """Create a TechSpecAgent instance."""
    return TechSpecAgent(client=client)