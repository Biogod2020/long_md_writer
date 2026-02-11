"""
Refiner Agent: Transforms raw user input + clarification answers into a structured Project Brief.
This agent is DOMAIN-AGNOSTIC. All specificity comes from user input.
"""

from typing import Optional
from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


REFINER_SYSTEM_PROMPT = """You are an expert requirements analyst and creative strategist. Your task is to synthesize the user's input, uploaded materials, and their answers into a comprehensive **Project Brief**.

This Project Brief acts as the "North Star" for the entire project, ensuring the Architect, Writer, and Designer are perfectly aligned.

### Design Philosophy
1. **Adaptive Structure**: Do NOT feel forced into a fixed layout. If the user wants a slide deck, the brief should reflect slide-specific requirements.
2. **Input-Driven**: Every requirement must be grounded in the user's intent and provided materials.
3. **SOTA Aesthetic & Quality**: Establish a high-level "Visual Identity." Define the project's design DNA (e.g., professional textures, clarity, spatial rhythm).

### Suggested Components
- **Vision & Goals**: The core mission and "Conceptual Anchor."
- **Visual Identity & Narrative**: Define the design direction and visual vibe. Include details on color palettes, typography, and material styles (e.g., minimalist industrial, clean professional, high-contrast clarity).
- **Tone, Style & Rigor**: Academic, narrative, or professional? Determine the level of technical density.
- **Structural Constraints**: Specific sections, flow, or non-linear requirements.
- **Visual & Interactive Intent**: Detailed list of expected animations, diagrams, and interactive components.
- **Knowledge Core**: Key concepts and logic chains that MUST be integrated.

### Rules
1. **No Hallucinations**: Base everything on provided context. If something is unknown, state it.
2. **Formatting**: Use clean Markdown.
3. **Language**: Generate the Project Brief in the SAME LANGUAGE as the user's input.
"""


class RefinerAgent:
    """Refines user input into a structured Project Brief."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
        
    def run(self, state: AgentState, clarification_answers: Optional[dict] = None, feedback: Optional[str] = None) -> str:
        """
        Run the Refiner.
        
        Args:
            state: AgentState with user_intent and images.
            clarification_answers: Dict mapping question IDs to user answers.
            feedback: Optional user feedback for refinement.
            
        Returns:
            Structured Project Brief as Markdown.
        """
        parts = []
        
        # 1. Project Context
        if state.project_brief:
            parts.append({"text": "# Current Project Brief\n" + state.project_brief + "\n\n"})
            if feedback:
                parts.append({"text": "# User Feedback\n" + feedback + "\n\n" + "Please refine the brief based on this feedback.\n\n"})
        
        # 2. User's Intent (Instruction)
        parts.append({"text": "# 🎯 User Intent (Instruction)\n" + state.user_intent + "\n\n"})
        
        # 3. Reference Materials (Full Text)
        if state.reference_materials:
            parts.append({"text": "# 📚 Reference Materials (Full Text)\n" + state.reference_materials + "\n\n"})
        
        # 4. (Legacy) Uploaded reference documents by path
        if state.reference_doc_paths:
            from pathlib import Path
            ref_text = ["# Uploaded Reference Documents (Paths)\n"]
            for doc_path in state.reference_doc_paths:
                try:
                    content = Path(doc_path).read_text(encoding="utf-8")
                    ref_text.append(f"## {Path(doc_path).name}\n{content}\n\n")
                except Exception:
                    pass
            parts.append({"text": "".join(ref_text)})
        
        # 3. Images
        if state.images:
            parts.extend(state.images)
            parts.append({"text": "\n(Images provided above)\n\n"})
        
        # 4. Clarification Q&A
        if clarification_answers:
            qa_text = ["# Clarification Q&A\n"]
            for qid, answer in clarification_answers.items():
                qa_text.append(f"- **{qid}**: {answer}\n")
            parts.append({"text": "".join(qa_text) + "\n"})
        
        parts.append({"text": "\nBased on all the above, generate a comprehensive Project Brief.\n"})
        
        response = self.client.generate(
            parts=parts,
            system_instruction=REFINER_SYSTEM_PROMPT,
            temperature=0.7,
            stream=True  # 启用流式生成以避免 500 SSL 超时
        )
        
        if response.success:
            return response.text
        else:
            return f"Refinement failed: {response.error}"

    async def run_async(self, state: AgentState, clarification_answers: Optional[dict] = None, feedback: Optional[str] = None) -> str:
        """异步版本"""
        parts = []

        if state.project_brief:
            parts.append({"text": "# Current Project Brief\n" + state.project_brief + "\n\n"})
            if feedback:
                parts.append({"text": "# User Feedback\n" + feedback + "\n\nPlease refine the brief based on this feedback.\n\n"})

        parts.append({"text": "# 🎯 User Intent (Instruction)\n" + state.user_intent + "\n\n"})

        if state.reference_materials:
            parts.append({"text": "# 📚 Reference Materials (Full Text)\n" + state.reference_materials + "\n\n"})

        if state.reference_doc_paths:
            from pathlib import Path
            ref_text = ["# Uploaded Reference Documents (Paths)\n"]
            for doc_path in state.reference_doc_paths:
                try:
                    content = Path(doc_path).read_text(encoding="utf-8")
                    ref_text.append(f"## {Path(doc_path).name}\n{content}\n\n")
                except Exception:
                    pass
            parts.append({"text": "".join(ref_text)})

        if state.images:
            parts.extend(state.images)
            parts.append({"text": "\n(Images provided above)\n\n"})

        if clarification_answers:
            qa_text = ["# Clarification Q&A\n"]
            for qid, answer in clarification_answers.items():
                qa_text.append(f"- **{qid}**: {answer}\n")
            parts.append({"text": "".join(qa_text) + "\n"})

        parts.append({"text": "\nBased on all the above, generate a comprehensive Project Brief.\n"})

        response = await self.client.generate_async(
            parts=parts,
            system_instruction=REFINER_SYSTEM_PROMPT,
            temperature=0.7,
            stream=True
        )

        if response.success:
            return response.text
        else:
            return f"Refinement failed: {response.error}"


def create_refiner_agent(client: Optional[GeminiClient] = None) -> RefinerAgent:
    """Create a RefinerAgent instance."""
    return RefinerAgent(client=client)