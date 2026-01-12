"""
Node 1: Architect Agent (首席架构师)
负责语义拆解，输出详细目录 (Manifest)
"""

import json
from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import Manifest, SectionInfo, AgentState


# 灵活的 Manifest Schema - 强制核心必填字段，允许 API 自由扩展元数据
FLEXIBLE_MANIFEST_SCHEMA = {
    "type": "object",
    "properties": {
        "project_title": {"type": "string"},
        "description": {"type": "string"},
        "config": {"type": "object"},
        "metadata": {"type": "object"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "estimated_words": {"type": "integer"},
                    "metadata": {"type": "object"}
                },
                "required": ["id", "title", "summary"]
            }
        },
        "knowledge_map": {"type": "object"}
    },
    "required": ["project_title", "description", "sections"]
}

ARCHITECT_SYSTEM_PROMPT = r"""You are the **Chief Content Architect**. Your task is to design a world-class, SOTA (State-of-the-Art) document structure.

### Adaptive Thinking (SOTA)
You are NOT limited to standard book-like structures. If the Project Brief suggest a slide deck, a cinematic narrative, or a multi-modal technical guide, your Manifest must reflect that. 
- **Non-Linear Flow**: Sections don't have to be just "Chapter 1, 2, 3". They can be "Phase 1: Foundations", "Deep Dive: The Vector Lab (Interactive)", etc.
- **Visual Rhythm**: Think about the pacing. Where should we have a high-impact split layout? Where should we have a dense technical proof?

### Core Design Principles
1. **First Principles Architecture**: Derive high-level applications (clinical ECG) from basic mechanisms (the ion flux dipole).
2. **Pedagogical Soul**: Every section must have a "Conceptual Anchor"—a specific mechanism or "Aha!" moment it targets.
3. **Adaptive Manifest**: Use the `metadata` and `config` fields to provide rich instructions for downstream agents (e.g., layout, visual intent, interactivity logic, GSAP cues).
4. **SOTA Standards**: Aim for the structural depth of top-tier educational materials (e.g., *Robbins Pathology*, *The Feynman Lectures*).
5. **Image Sourcing (MANDATORY)**: The user explicitly wants "internet-sourced images". You **MUST** include an `image_search_queries` list in the `metadata` of **EVERY** section that could benefit from a visual.
    -   This list MUST contain 1-2 specific, high-quality search terms (e.g., ['ECG lead placement anatomical diagram', 'cardiac vector projection illustration']).
    -   **DO NOT OMIT THIS**. If a section describes a concept, it needs an image query.

### Output Format (JSON Only)
- Output **pure JSON**.
- Escape backslashes in LaTeX (e.g., `\\cdot`).
- **THE DESCRIPTION FIELD**: This is your "Project Vision & Technical Philosophy". It should be a 300-500 word manifesto on how this specific project achieves SOTA status through its structure and logic.

```json
{
  "project_title": "Magnificent Title",
  "author": "Magnum Opus AI",
  "description": "# Project Vision\nDetailed technical philosophy and architectural goals...",
  "config": {
    "theme": "dark | light | high-contrast",
    "layout_type": "slide | textbook | dashboard",
    "aesthetic_intent": "Futuristic HUD | Classic Academic | Minimalist Lab",
    "extra_scripts": ["https://cdn..."]
  },
  "sections": [
    {
      "id": "slide-01",
      "title": "The Dipole Singularity",
      "summary": "A 100+ word narrative summary describing exactly what happens in this section/slide. Mention the 'Conceptual Anchor'.",
      "estimated_words": 600,
      "metadata": {
         "layout": "standard | split | hero | grid",
         "visual_intent": "High-pacing vector growth animation",
         "has_interactive_element": true,
         "interaction_logic": "SVG Drag-and-drop dipole simulator",
         "priority": "critical",
         "image_search_queries": ["electric dipole moment physics diagram", "cardiac vector projection"]
      }
    }
  ],
  "knowledge_map": { "slide-01": ["Concept A", "Concept B"] },
  "metadata": { "global_visual_rigor": "high", "hud_elements": ["Logic Tree", "Live Readouts"] }
}
```
"""


class ArchitectAgent:
    """首席架构师 Agent"""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState, feedback: Optional[str] = None) -> AgentState:
        """
        Run the Architect Agent.
        
        Args:
            state: AgentState
            feedback: Optional feedback for revision.
            
        Returns:
            Updated AgentState.
        """
        # 1. Build prompt parts (incorporating full context)
        parts = self._build_prompt_parts(state, feedback)
        
        # 如果有反馈，降低温度以提高指令遵循度
        # Strict adherence mode for feedback
        if feedback:
            parts.append({
                "text": f"CRITICAL USER FEEDBACK: {feedback}\n\nYou MUST adjust the manifest to comply with this feedback. If the user asks to reduce word count, you MUST reduce 'estimated_words'. If the user asks to fix JSON, you MUST fix the syntax."
            })
            temperature = 0.1  # Lower temperature for strict adherence
        else:
            temperature = 0.7

        # Retry loop for JSON correction
        MAX_RETRIES = 3
        last_error = None
        
        # 0. Forced fallback to standard generation (Structured Output info density is too low)
        pass
        """
        if hasattr(self.client, "generate_structured"):
            # ... (kept code for reference but disabled)
        """
        
        # Standard Retro Loop
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                print(f"    [Architect] JSON Error (Attempt {attempt}): {last_error}. Retrying with self-correction...")
                parts.append({
                    "text": f"SYSTEM: Your previous JSON output caused a parse error: {last_error}\nPlease output the full, valid JSON again, fixing this error. Ensure all quotes and brackets are matching."
                })
            
            response = self.client.generate(
                parts=parts,
                system_instruction=ARCHITECT_SYSTEM_PROMPT,
                temperature=temperature,
                stream=True  # 启用流式生成以避免 500 SSL 超时
            )
        
            # 调试日志：保存原始响应
            try:
                log_path = Path(state.workspace_path) / "architect_raw_response.txt"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(response.text, encoding="utf-8")
            except:
                pass

            if not response.success:
                error_msg = f"Architect Agent failed to generate: {response.error}"
                if attempt == MAX_RETRIES:
                    state.errors.append(error_msg)
                    return state
                last_error = response.error
                continue
            
            # 解析 manifest
            try:
                manifest = self._parse_manifest(response.text)
                state.manifest = manifest
                
                # 保存 manifest 到工作目录
                self._save_manifest(state)
                
                return state
                
            except Exception as e:
                # JSON parse failed
                last_error = str(e)
                if attempt == MAX_RETRIES:
                    state.errors.append(f"Failed to parse manifest after {MAX_RETRIES} retries: {str(e)}")
                    # 如果解析失败，把解析用的 cleaned content 也存一下方便排查
                    try:
                        debug_path = Path(state.workspace_path) / "manifest_parse_error_content.txt"
                        debug_path.write_text(response.text, encoding="utf-8")
                    except:
                        pass
                    return state
                # Continue loop to retry
        
        return state
    
    def _build_prompt_parts(self, state: AgentState, feedback: Optional[str] = None) -> list[dict]:
        """
        Build prompt parts using Context Chain (Residual Connection).
        
        关键规划节点使用 state.user_context 注入完整用户意图。
        """
        final_parts = []
        
        # 1. Revision Mode (if manifest exists)
        if state.manifest:
            current_json = state.manifest.model_dump_json(indent=2)
            revision_context = f"# Revision Mode\nModify existing Manifest based on feedback:\n\n{current_json}\n"
            if feedback:
                revision_context += f"\nFEEDBACK: {feedback}\n"
            final_parts.append({"text": revision_context})
        
        # 2. USER CONTEXT (Residual Connection) - 核心用户意图注入
        if state.user_context:
            final_parts.append({"text": state.user_context})
        
        # 3. Reference docs (if any)
        if state.reference_docs:
            ref_parts = ["# 参考资料\n"]
            for doc in state.reference_docs:
                try:
                    text = Path(doc).read_text(encoding="utf-8")
                    ref_parts.append(f"### File: {doc}\n{text}\n")
                except:
                    pass
            if len(ref_parts) > 1:
                final_parts.append({"text": "\n".join(ref_parts)})
        
        # 4. Images (if any)
        if hasattr(state, "images") and state.images:
            final_parts.extend(state.images)
            final_parts.append({"text": "\n(Visual references above)\n"})

        # 5. Task instruction
        if not state.manifest:
            final_parts.insert(0, {"text": "Generate a SOTA Manifest JSON based on the following user context. Be adaptive and creative with the structure and metadata.\n"})
            
        return final_parts
    
    def _parse_manifest(self, text: str) -> Manifest:
        """解析 Manifest JSON (增强鲁棒性)"""
        import re
        
        cleaned = text.strip()
        
        # 尝试寻找 最外层的 JSON 块 (贪婪匹配首尾大括号)
        # Find the FIRST valid opening brace and LAST valid closing brace
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        
        if start != -1 and end != -1:
            cleaned = cleaned[start:end+1]
        
        # 尝试清理一些常见的 JSON 错误 (Best Effort)
        # 1. 修复 "id": "sec-6": "Title" -> "id": "sec-6", "title": "Title"
        # 这是一个特定修复，针对 LLM 常见的结构错误
        cleaned = re.sub(
            r'\"id\":\s*\"(sec-\d+)\":\s*\"([^\"]+)\"',
            r'"id": "\1", "title": "\2"',
            cleaned
        )
        
        data = json.loads(cleaned)
        
        # 转换 sections
        sections = []
        for sec_data in data.get("sections", []):
            sections.append(SectionInfo(
                id=sec_data["id"],
                title=sec_data["title"],
                summary=sec_data.get("summary", ""),
                estimated_words=sec_data.get("estimated_words", 0),
                metadata=sec_data.get("metadata", {})
            ))
        
        return Manifest(
            project_title=data.get("project_title", "Untitled"),
            author=data.get("author"),
            description=data.get("description", ""),
            config=data.get("config", {}),
            metadata=data.get("metadata", {}),
            sections=sections,
            knowledge_map=data.get("knowledge_map", {}),
        )
    
    def _save_manifest(self, state: AgentState) -> None:
        """保存 Manifest 到工作目录"""
        if not state.manifest:
            return

        manifest_path = Path(state.workspace_path) / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        manifest_path.write_text(
            state.manifest.model_dump_json(indent=2),
            encoding="utf-8"
        )

    async def run_async(self, state: AgentState, feedback: Optional[str] = None) -> AgentState:
        """异步版本"""
        parts = self._build_prompt_parts(state, feedback)

        if feedback:
            parts.append({
                "text": f"CRITICAL USER FEEDBACK: {feedback}\n\nYou MUST adjust the manifest to comply with this feedback."
            })
            temperature = 0.1
        else:
            temperature = 0.7

        MAX_RETRIES = 3
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                print(f"    [Architect] JSON Error (Attempt {attempt}): {last_error}. Retrying...")
                parts.append({
                    "text": f"SYSTEM: Your previous JSON output caused a parse error: {last_error}\nPlease output the full, valid JSON again."
                })

            response = await self.client.generate_async(
                parts=parts,
                system_instruction=ARCHITECT_SYSTEM_PROMPT,
                temperature=temperature,
                stream=True
            )

            if not response.success:
                error_msg = f"Architect Agent failed: {response.error}"
                if attempt == MAX_RETRIES:
                    state.errors.append(error_msg)
                    return state
                last_error = response.error
                continue

            try:
                manifest = self._parse_manifest(response.text)
                state.manifest = manifest
                self._save_manifest(state)
                return state
            except Exception as e:
                last_error = str(e)
                if attempt == MAX_RETRIES:
                    state.errors.append(f"Failed to parse manifest: {str(e)}")
                    return state

        return state


def create_architect_agent(client: Optional[GeminiClient] = None) -> ArchitectAgent:
    """创建架构师 Agent 实例"""
    return ArchitectAgent(client=client)
