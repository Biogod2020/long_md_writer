"""
ClarifierAgent: Asks targeted clarifying questions to understand user intent.
This agent runs BEFORE the Refiner to gather missing information.
"""

from typing import Optional
from ..core.gemini_client import GeminiClient
from ..core.types import AgentState


CLARIFIER_SYSTEM_PROMPT = """You are an expert technical project analyst. Your task is to analyze the user's intent and ask targeted clarifying questions to bridge the gap between their raw request and a SOTA technical production.

### Adaptive Reasoning
Do NOT stick to a fixed number of questions. Use your judgment:
- If the request is simple and clear, ask 1-2 sharp questions.
- If the request is complex or vague (e.g., "build a training course"), ask 5-7 deep questions covering structure, interactive needs, and technical depth.
- **Layout Identification**: Pay special attention to whether the user wants a standard document, slides, a dashboard, or a lab manual. Ask questions that help define the `layout_type`.

### Question Categories
- **Strategic Goal**: What is the ultimate outcome?
- **Technical Rigor**: Level of depth (First-principles vs. high-level)?
- **Visual/UX Architecture**: Does this require specific interactive components (animations, code runners, slide transitions)?
- **Audience Context**: Background and prerequisite knowledge?

### Output Format
Return a JSON array of questions.
```json
[
  {"id": "q1", "category": "layout", "question": "Since you mentioned a training course, would a slide-based layout with interactive labs be more effective than a static document?"},
  ...
]
```
**Language**: Always match the language of the user's input.
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
        parts.append({"text": "# 🎯 User Intent (Instruction)\n" + state.user_intent + "\n\n"})
        
        # 2. Uploaded files summary
        if state.reference_doc_paths:
            parts.append({"text": f"# Uploaded Files\nThe user has uploaded {len(state.reference_doc_paths)} file(s).\n"})
        
        # 3. Images if any
        if state.images:
            parts.extend(state.images)
            parts.append({"text": "\n(Images provided above)\n"})
        
        parts.append({"text": "\nBased on the above input, generate 3-5 clarifying questions to better understand the user's requirements.\n"})
        
        if hasattr(self.client, "generate_structured"):
            try:
                # Need to manually construct prompt string from parts
                # Usually Clarifier has simple text parts
                prompt_text = "\n".join([p["text"] for p in parts])
                
                print("    [Clarifier] Using Structured Output (JSON Schema)...")
                schema = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "category": {"type": "string"},
                            "question": {"type": "string"}
                        },
                        "required": ["id", "category", "question"]
                    }
                }
                
                response = self.client.generate_structured(
                    prompt=prompt_text,
                    response_schema=schema,
                    schema_name="ClarificationQuestions",
                    system_instruction=CLARIFIER_SYSTEM_PROMPT,
                    temperature=0.7
                )
                
                if response.success and response.json_data:
                    return response.json_data
                else:
                    print(f"    [Clarifier] Structured generation failed: {response.error}. Falling back...")
            except Exception as e:
                print(f"    [Clarifier] Structured generation error: {e}. Falling back...")

        response = self.client.generate(
            parts=parts,
            system_instruction=CLARIFIER_SYSTEM_PROMPT,
            temperature=0.7,
            stream=True  # 启用流式生成以避免 500 SSL 超时
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

    async def run_async(self, state: AgentState) -> list[dict]:
        """
        异步版本 - 避免 asyncio.run() 嵌套问题
        """
        parts = []
        parts.append({"text": "# 🎯 User Intent (Instruction)\n" + state.user_intent + "\n\n"})

        if state.reference_doc_paths:
            parts.append({"text": f"# Uploaded Files\nThe user has uploaded {len(state.reference_doc_paths)} file(s).\n"})

        if state.images:
            parts.extend(state.images)
            parts.append({"text": "\n(Images provided above)\n"})

        parts.append({"text": "\nBased on the above input, generate 3-5 clarifying questions to better understand the user's requirements.\n"})

        # 使用异步生成
        response = await self.client.generate_async(
            parts=parts,
            system_instruction=CLARIFIER_SYSTEM_PROMPT,
            temperature=0.7,
            stream=True
        )

        if not response.success:
            return [{"id": "error", "category": "error", "question": f"Failed to generate questions: {response.error}"}]

        return self._parse_questions(response.text)


def create_clarifier_agent(client: Optional[GeminiClient] = None) -> ClarifierAgent:
    """Create a ClarifierAgent instance."""
    return ClarifierAgent(client=client)
