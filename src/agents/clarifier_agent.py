"""
ClarifierAgent: Asks targeted clarifying questions to understand user intent.
This agent runs BEFORE the Refiner to gather missing information.
"""

from typing import Optional
from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import AgentState


CLARIFIER_SYSTEM_PROMPT = """You are an expert project analyst. Your task is to analyze the user's initial input and ask 3-5 targeted clarifying questions to ensure the final output perfectly matches their expectations.

### Your Role
You help users articulate their needs for generating long-form HTML documents (lectures, tutorials, documentation, etc.). You do NOT make assumptions about the domain or content type.

### Question Categories (choose relevant ones)
1. **Target Audience**: Who will read this? What is their background?
2. **Content Depth**: Should this be introductory, intermediate, or advanced?
3. **Pedagogical Approach**: Prefer step-by-step derivations, examples-first, or conceptual overviews?
4. **Visual & Interactive Elements**: Do they want animations, interactive diagrams, slides, or static content?
5. **Length & Structure**: How many sections? Estimated total words?
6. **Tone & Style**: Academic, conversational, technical, or casual?

### Output Format
Return a JSON array of questions. Each question should be:
- Clear and specific
- Non-leading (don't suggest an answer)
- Directly actionable

```json
[
  {"id": "q1", "category": "audience", "question": "Who is the primary audience for this document?"},
  {"id": "q2", "category": "depth", "question": "..."},
  ...
]
```
"""


class ClarifierAgent:
    """Agent that asks clarifying questions before refinement."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState) -> list[dict]:
        """
        Analyze user input and generate clarifying questions.
        
        Returns:
            List of question dictionaries with id, category, and question text.
        """
        parts = []
        
        # 1. User's raw input
        parts.append({"text": "# User's Initial Input\n" + state.raw_materials + "\n\n"})
        
        # 2. Uploaded files summary
        if state.reference_docs:
            parts.append({"text": f"# Uploaded Files\nThe user has uploaded {len(state.reference_docs)} file(s).\n"})
        
        # 3. Images if any
        if state.images:
            parts.extend(state.images)
            parts.append({"text": "\n(Images provided above)\n"})
        
        parts.append({"text": "\nBased on the above input, generate 3-5 clarifying questions to better understand the user's requirements.\n"})
        
        response = self.client.generate(
            parts=parts,
            system_instruction=CLARIFIER_SYSTEM_PROMPT,
            temperature=0.7
        )
        
        if not response.success:
            return [{"id": "error", "category": "error", "question": f"Failed to generate questions: {response.error}"}]
        
        # Parse questions from response
        return self._parse_questions(response.text)
    
    def _parse_questions(self, text: str) -> list[dict]:
        """Extract questions from LLM response."""
        import json
        import re
        
        cleaned = text.strip()
        
        # Try to find JSON array
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Fallback: extract questions manually
        questions = []
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '?' in line:
                questions.append({
                    "id": f"q{i+1}",
                    "category": "general",
                    "question": line.strip().strip('-').strip('*').strip()
                })
        
        return questions[:5] if questions else [{"id": "q1", "category": "general", "question": "Could you describe your target audience and the desired depth of content?"}]


def create_clarifier_agent(client: Optional[GeminiClient] = None) -> ClarifierAgent:
    """Create a ClarifierAgent instance."""
    return ClarifierAgent(client=client)
