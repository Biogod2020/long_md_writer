"""
Refiner Agent: Transforms raw user input + clarification answers into a structured Project Brief.
This agent is DOMAIN-AGNOSTIC. All specificity comes from user input.
"""

from typing import Optional
from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


REFINER_SYSTEM_PROMPT = """You are an expert requirements analyst. Your task is to synthesize the user's input, uploaded materials, and their answers to clarifying questions into a clear, structured **Project Brief**.

This Project Brief will be the foundation for the entire project, guiding the Architect, Writer, and Designer.

### Design Philosophy
1. **Adaptive Structure**: Do NOT feel forced into a fixed layout. If the user wants a slide deck, the brief should reflect slide-specific requirements. If they want a technical deep-dive, focus on rigor and depth.
2. **Input-Driven**: Every section of your brief should be derived from the user's intent and the provided raw materials. 
3. **SOTA Quality**: Act as a senior consultant. Identify not just the "what", but the "how" and "why" behind the user's request.

### Suggested (but not mandatory) Components
A high-quality brief typically covers:
- **Vision & Goals**: The "North Star" of the project.
- **Target Audience & Context**: Who is this for and where will it be hosted?
- **Tone, Style & Rigor**: Academic, casual, professional? High-math or conceptual?
- **Structural Constraints**: Specific sections or flow requested.
- **Visual & Interactive Intent**: Detailed list of animations, interactive components, or specific design aesthetics (e.g., glassmorphism, neo-tokyo style).
- **Core Knowledge Extraction**: Key concepts that MUST be integrated.

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
            state: AgentState with raw_materials and images.
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
        
        # 2. User's original input
        parts.append({"text": "# User's Original Input\n" + state.raw_materials + "\n\n"})
        
        # 2. Uploaded reference documents
        if state.reference_docs:
            from pathlib import Path
            ref_text = ["# Uploaded Reference Materials\n"]
            for doc_path in state.reference_docs:
                try:
                    content = Path(doc_path).read_text(encoding="utf-8")
                    ref_text.append(f"## {Path(doc_path).name}\n{content[:10000]}...\n\n")
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


def create_refiner_agent(client: Optional[GeminiClient] = None) -> RefinerAgent:
    """Create a RefinerAgent instance."""
    return RefinerAgent(client=client)
