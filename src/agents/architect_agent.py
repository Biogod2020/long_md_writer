"""
Node 1: Architect Agent (首席架构师)
负责语义拆解，输出详细目录 (Manifest)
"""

import json
from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient
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

ARCHITECT_SYSTEM_PROMPT = r"""You are the **Chief Content Architect**. Your mission is to design a SOTA (State-of-the-Art) document structure that balances intellectual rigor with professional visual clarity.

### Visual Architecture (SOTA)
You are not just a table-of-contents generator; you are a visual editor. 
- **Visual Rhythm & Pacing**: Think about the "pacing" of the document. Where should we have a high-impact "Hero" section? Where should we slow down for "Microscopic Detail"?
- **Compositional Balance**: For each section, define the "Visual Goal" (e.g., "The relationship between components and the whole system").
- **Adaptive Layouts**: Use metadata to suggest layouts like "Hero," "Split-Screen," or "Grid" based on the content's importance and visual potential.

### Core Design Principles
1. **First Principles Logic**: Derive complex applications from fundamental mechanisms.
2. **Pedagogical Soul**: Every section must have a "Conceptual Anchor"—a specific "Aha!" moment or mechanism it targets.
3. **High-Fidelity Metadata**: Use `metadata` and `config` to provide rich instructions for downstream agents (e.g., visual intent, atmosphere cues, interactive logic).
4. **Professional Depth**: Aim for the structural sophistication of premium technical publications.

### Output Format (JSON Only)
- Output **pure JSON**.
- Escape backslashes in LaTeX (e.g., `\\cdot`).
- **THE DESCRIPTION FIELD**: This is your "Architectural Manifesto". It should be a 300-500 word technical and aesthetic philosophy on how this specific structure achieves a SOTA experience.

```json
{
  "project_title": "Elevated Project Title",
  "author": "Magnum Opus AI",
  "description": "# Architectural Manifesto\nDetailed technical and aesthetic philosophy...",
  "config": {
    "theme": "dark | light | adaptive",
    "layout_type": "slide | textbook | immersive",
    "aesthetic_intent": "Define the Visual DNA (e.g., Minimalist Lab, Industrial Professional)",
    "extra_scripts": []
  },
  "sections": [
    {
      "id": "sec-01",
      "title": "The Conceptual Entry",
      "summary": "A 100+ word narrative summary defining the 'Visual Context' and core mechanism.",
      "estimated_words": 600,
      "metadata": {
         "layout": "standard | split | hero | panorama",
         "visual_intent": "Professional visual goal (e.g., 'A detailed breakdown of the internal components')",
         "visual_tension": "Describe the core visual contrast or focus needed here",
         "image_search_queries": ["Specific keywords for high-quality sourcing"]
      }
    }
  ],
  "knowledge_map": { "sec-01": ["Concept A"] },
  "metadata": { "professional_rigor": "high", "visual_pacing": "dynamic" }
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
            except Exception:
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
                    except Exception:
                        pass
                    return state
                # Continue loop to retry
        
        return state
    
    def _build_prompt_parts(self, state: AgentState, feedback: Optional[str] = None) -> list[dict]:
        """
        Build prompt parts using Context Chain (Residual Connection).
        
        关键规划节点使用 state.user_context 注入完整用户意图。
        支持多模态注入 MANDATORY 资产。
        """
        final_parts = []
        
        # 1. USER CONTEXT (Residual Connection) - 核心用户意图注入
        if state.user_context:
            final_parts.append({"text": state.user_context})
        
        # 2. MANDATORY ASSETS (Multimodal Injection)
        uar = state.get_uar()
        mandatory_assets = [a for a in uar.assets.values() if a.priority == "MANDATORY"]
        
        if mandatory_assets:
            instr = "\n## ⚠️ 强制性资产清单 (Required Assets)\n"
            instr += "以下资产由用户提供且**必须**在 Manifest 中进行规划。请在合适的章节 metadata 中，通过 `assigned_assets` 字段（资产 ID 列表）进行硬性分配。\n\n"
            for a in mandatory_assets:
                instr += f"- **[{a.id}]**: {a.semantic_label}\n"
            
            final_parts.append({"text": instr})
            
            # 注入图片数据
            for a in mandatory_assets:
                if a.base64_data:
                    final_parts.append({
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": a.base64_data
                        }
                    })
                    final_parts.append({"text": f"*(图片: {a.id})*\n"})

        # 3. Reference Materials (full text)
        if state.reference_materials:
            final_parts.append({"text": f"\n# 📚 参考资料全文\n{state.reference_materials}\n"})
        
        # 4. Reference docs by path (legacy/追踪)
        if state.reference_doc_paths:
            ref_parts = ["# 额外参考文件\n"]
            for doc in state.reference_doc_paths:
                try:
                    text = Path(doc).read_text(encoding="utf-8")
                    ref_parts.append(f"### File: {doc}\n{text}\n")
                except Exception:
                    pass
            if len(ref_parts) > 1:
                final_parts.append({"text": "\n".join(ref_parts)})
        
        # 5. Revision Mode (if manifest exists)
        if state.manifest:
            current_json = state.manifest.model_dump_json(indent=2)
            revision_context = f"# Revision Mode\nModify existing Manifest based on feedback:\n\n{current_json}\n"
            if feedback:
                revision_context += f"\nFEEDBACK: {feedback}\n"
            final_parts.append({"text": revision_context})

        # 6. Task instruction
        if not state.manifest:
            final_parts.insert(0, {"text": "Generate a SOTA Manifest JSON based on the following user context. Be adaptive, cinematic, and detailed with visual metadata.\n"})
            
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
        """异步版本 - 使用 Native Structured Output"""
        parts = self._build_prompt_parts(state, feedback)

        if feedback:
            parts.append({
                "text": f"CRITICAL USER FEEDBACK: {feedback}\n\nYou MUST adjust the manifest to comply with this feedback."
            })
            temperature = 0.1
        else:
            temperature = 0.7

        print("    [Architect] Generating manifest using Native JSON Mode...")
        
        # Use native structured generation
        prompt_text = "\n".join([p.get("text", "") for p in parts if "text" in p])
        response = await self.client.generate_structured_async(
            prompt=prompt_text,
            response_schema=FLEXIBLE_MANIFEST_SCHEMA,
            system_instruction=ARCHITECT_SYSTEM_PROMPT,
            temperature=temperature
        )

        if not response.success:
            state.errors.append(f"Architect Agent failed: {response.error}")
            return state

        # Capture thoughts
        if response.thoughts:
            state.thoughts = response.thoughts

        try:
            # Parse manifest from JSON data
            data = response.json_data if response.json_data else self._parse_manifest(response.text)
            
            # Convert to Manifest object
            sections = []
            for sec_data in data.get("sections", []):
                sections.append(SectionInfo(
                    id=sec_data["id"],
                    title=sec_data["title"],
                    summary=sec_data.get("summary", ""),
                    estimated_words=sec_data.get("estimated_words", 0),
                    metadata=sec_data.get("metadata", {})
                ))
            
            state.manifest = Manifest(
                project_title=data.get("project_title", "Untitled"),
                author=data.get("author"),
                description=data.get("description", ""),
                config=data.get("config", {}),
                metadata=data.get("metadata", {}),
                sections=sections,
                knowledge_map=data.get("knowledge_map", {}),
            )
            
            self._save_manifest(state)
            return state
            
        except Exception as e:
            state.errors.append(f"Failed to process manifest structure: {str(e)}")
            return state

    def run(self, state: AgentState, feedback: Optional[str] = None) -> AgentState:
        """同步版本 - 封装异步调用"""
        import asyncio
        return asyncio.run(self.run_async(state, feedback))