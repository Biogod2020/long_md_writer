"""
OutlineAgent: Generates ONLY the high-level document structure.
Does NOT generate technical implementation details - that's TechSpecAgent's job.
"""

from pathlib import Path
import json
from typing import Optional

from ..core.gemini_client import GeminiClient
from ..core.types import Manifest, SectionInfo, AgentState


OUTLINE_SYSTEM_PROMPT = """You are an expert document architect. Your ONLY task is to design the high-level structure (outline) of a long-form document based on the Project Brief.

### Your Role
- Design the logical flow of the document.
- Create section titles and summaries.
- Ensure proper sequencing (foundations before advanced topics).
- Do NOT include any technical implementation details (CSS, animations, etc.).

### Output Format (JSON)
```json
{
  "project_title": "Compelling title for the document",
  "author": "Magnum Opus AI",
  "sections": [
    {
      "id": "sec-1",
      "title": "Section Title",
      "summary": "Detailed 50-100 word summary explaining what this section covers and why it comes at this position.",
      "estimated_words": 2500
    }
  ],
  "knowledge_map": {
    "sec-1": ["Concept A", "Concept B"]
  }
}
```

### Rules
1. Generate 5-10 sections for a comprehensive document.
2. Each summary must be 50-100 words explaining the section's purpose.
3. Section order must follow logical learning progression.
4. Do NOT include any CSS, animation, or visual design specifications.
5. Output ONLY valid JSON, no markdown code blocks.
"""


class OutlineAgent:
    """Generates document structure outline only."""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState, feedback: Optional[str] = None) -> AgentState:
        """
        Generate document outline based on Project Brief.
        
        Args:
            state: AgentState with project_brief populated.
            feedback: Optional user feedback for refinement.
            
        Returns:
            AgentState with manifest (without description) populated.
        """
        parts = []
        
        # 1. Previous Manifest (if exists)
        if state.manifest and feedback:
            parts.append({"text": "# Current Outline\n" + state.manifest.model_dump_json() + "\n\n"})
            parts.append({"text": "# User Feedback\n" + feedback + "\n\n" + "Please refine the outline based on this feedback.\n\n"})
        
        # 2. Project Brief
        if state.project_brief:
            parts.append({"text": "# Project Brief\n" + state.project_brief + "\n\n"})
        else:
            parts.append({"text": "# Raw Requirements\n" + state.raw_materials + "\n\n"})
        
        # 3. Raw Materials (ALWAYS include as reference for deeper context)
        if state.raw_materials:
            # Include raw materials regardless of whether project_brief exists
            # This provides the original source content for more accurate outline design
            parts.append({"text": "# Original Source Materials (Reference)\n" + state.raw_materials + "\n\n"})
        
        parts.append({"text": "Based on the above Project Brief and source materials, design a comprehensive document outline.\n"})
        
        if hasattr(self.client, "generate_structured"):
            try:
                # Construct prompt text from parts
                prompt_text = "\n".join([p["text"] for p in parts])
                
                print("    [Outline] Using Structured Output (JSON Schema)...")
                schema = {
                    "type": "object",
                    "properties": {
                        "project_title": {"type": "string"},
                        "author": {"type": "string"},
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "estimated_words": {"type": "integer"}
                                },
                                "required": ["id", "title", "summary", "estimated_words"]
                            }
                        },
                        "knowledge_map": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    },
                    "required": ["project_title", "sections"]
                }
                
                response = self.client.generate_structured(
                    prompt=prompt_text,
                    response_schema=schema,
                    schema_name="DocumentOutline",
                    system_instruction=OUTLINE_SYSTEM_PROMPT,
                    temperature=0.7
                )
                
                if response.success and response.json_data:
                    outline = response.json_data
                    state.manifest = Manifest(
                        project_title=outline.get("project_title", "Untitled"),
                        author=outline.get("author", "Magnum Opus AI"),
                        description="",
                        sections=[
                            SectionInfo(
                                id=s["id"],
                                title=s["title"],
                                summary=s.get("summary", ""),
                                estimated_words=s.get("estimated_words", 2000)
                            ) for s in outline.get("sections", [])
                        ],
                        knowledge_map=outline.get("knowledge_map", {})
                    )
                    self._save_outline(state)
                    # Helper to log struct response
                    try:
                        log_path = Path(state.workspace_path) / "outline_structured_response.txt"
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                        log_path.write_text(response.text, encoding="utf-8")
                    except: pass
                    
                    return state
                else:
                    print(f"    [Outline] Structured generation failed: {response.error}. Falling back...")
            except Exception as e:
                print(f"    [Outline] Structured generation error: {e}. Falling back...")

        response = self.client.generate(
            parts=parts,
            system_instruction=OUTLINE_SYSTEM_PROMPT,
            temperature=0.7,
            stream=True  # 启用流式生成以避免 500 SSL 超时
        )
        
        # Debug: save response
        try:
            log_path = Path(state.workspace_path) / "outline_raw_response.txt"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(response.text, encoding="utf-8")
        except:
            pass
        
        if not response.success:
            state.errors.append(f"OutlineAgent failed: {response.error}")
            return state
        
        try:
            outline = self._parse_outline(response.text)
            # Create manifest WITHOUT description (TechSpecAgent will add it)
            state.manifest = Manifest(
                project_title=outline.get("project_title", "Untitled"),
                author=outline.get("author", "Magnum Opus AI"),
                description="",  # Will be filled by TechSpecAgent
                sections=[
                    SectionInfo(
                        id=s["id"],
                        title=s["title"],
                        summary=s.get("summary", ""),
                        estimated_words=s.get("estimated_words", 2000)
                    ) for s in outline.get("sections", [])
                ],
                knowledge_map=outline.get("knowledge_map", {})
            )
            self._save_outline(state)
        except Exception as e:
            state.errors.append(f"Failed to parse outline: {e}")
        
        return state
    
    def _parse_outline(self, text: str) -> dict:
        """Parse outline JSON from LLM response."""
        import re
        
        cleaned = text.strip()
        
        # Remove markdown code blocks if present
        match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
        
        return json.loads(cleaned)
    
    def _save_outline(self, state: AgentState) -> None:
        """Save outline to workspace."""
        if not state.manifest:
            return
        outline_path = Path(state.workspace_path) / "outline.json"
        outline_path.parent.mkdir(parents=True, exist_ok=True)
        outline_path.write_text(
            state.manifest.model_dump_json(indent=2),
            encoding="utf-8"
        )


def create_outline_agent(client: Optional[GeminiClient] = None) -> OutlineAgent:
    """Create an OutlineAgent instance."""
    return OutlineAgent(client=client)
