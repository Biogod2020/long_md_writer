"""
Refiner Agent: Transforms raw user input + clarification answers into a structured Project Brief.
This agent is DOMAIN-AGNOSTIC. All specificity comes from user input.
"""

from typing import Optional
from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


REFINER_SYSTEM_PROMPT = """You are an expert requirements analyst. Your task is to synthesize the user's input, uploaded materials, and their answers to clarifying questions into a clear, structured **Project Brief**.

This Project Brief will guide all downstream agents (Architect, Writer, Designer, etc.).

### Output Structure (Markdown)
Generate a brief with the following sections:

# Project Brief

## 1. Project Overview
- One-sentence summary of what will be created.

## 2. Target Audience
- Who will read this? What is their background and prior knowledge?

## 3. Core Objectives
- What problem does this document solve?
- What should readers be able to do after reading?

## 4. Content Scope & Depth
- What topics MUST be covered?
- What is explicitly OUT OF SCOPE?
- Depth level: introductory / intermediate / advanced / expert

## 5. Pedagogical Approach
- Preferred teaching style (step-by-step derivations, examples-first, conceptual overview, etc.)

## 6. Visual & Interactive Requirements
- Static or interactive?
- Specific elements requested (animations, diagrams, slides, code demos, etc.)

## 7. Tone & Style
- Academic, conversational, technical, casual?

## 8. Key Topics Extracted
- Bullet list of main topics/concepts extracted from the source materials.

### Rules
1. Do NOT invent information. Base everything on the user's input.
2. If something is unclear even after clarification, mark it as [TBD].
3. Be specific and actionable.
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
            temperature=0.7
        )
        
        if response.success:
            return response.text
        else:
            return f"Refinement failed: {response.error}"


def create_refiner_agent(client: Optional[GeminiClient] = None) -> RefinerAgent:
    """Create a RefinerAgent instance."""
    return RefinerAgent(client=client)
