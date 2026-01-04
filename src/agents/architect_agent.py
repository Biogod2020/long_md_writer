"""
Node 1: Architect Agent (首席架构师)
负责语义拆解，输出详细目录 (Manifest)
"""

import json
from pathlib import Path
from typing import Optional

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import Manifest, SectionInfo, AgentState


ARCHITECT_SYSTEM_PROMPT = """你这是 **首席内容架构师 (Chief Content Architect)**。你的任务是设计世界级、SOTA (State-of-the-Art) 级别的长篇技术/学术文档结构。

我们要创作的内容不仅要准确，更要有深度、有逻辑、有见解。拒绝肤浅的罗列。

### 核心设计原则
1.  **逻辑推演 (First Principles)**：从基本原理出发（如生理机制、底层算法），推导出上层现象。
2.  **深度优先 (Depth First)**：每个章节都必须深入探讨"为什么 (Why)"和"机制 (Mechanism)"，而不仅是"是什么 (What)"。
3.  **系统性 (Systematic)**：章节之间必须有严密的逻辑承接关系，构建完整的认知图谱。
4.  **SOTA 标准**：对标顶级教科书（如 *Robbins Pathology*, *SICP*, *Deep Learning Book*）的结构深度。

### 任务流程
1.  **分析需求**：仔细阅读「项目需求书 (Project Brief)」和参考材料。
2.  **结构设计**：
    - 设计宏大的篇章结构（Part -> Section）。
    - 确保包含必要的铺垫（Foundations）、核心机制（Core Mechanisms）、应用与病理（Applications/Pathology）、高阶综合（Synthesis）。
3.  **生成全景描述 (SOTA Description)**：
    - 在 `description` 中不仅要总结宗旨，还要包含 **技术执行指令**。
    - 明确指出后续 Agent 应该采用的：视觉风格、SVG 动画实现思路（如：利用 CSS @keyframes 模拟离子流动）、交互式 Slide 的设计建议、CSS 玻璃拟态效果等。
    - **该 Description 将作为后续所有 Agent 的全局系统指令**。
4.  **生成章节元数据**：
    - **ID**: `sec-1`, `sec-2`...
    - **Title**: 专业、精准的标题。
    - **Summary**: 必须详细！解释该章节的核心论点、覆盖的关键机制和逻辑目标。**少于 100 字的摘要是不合格的**。
    - **Estimated Words**: 基于深度估算，通常核心章节应在 2000-5000 字。

### 输入处理与修订
- 如果提供了 **Existing Manifest** 和 **User Feedback**，你必须基于反馈 **修改** 现有的结构。
- 解释你的修改逻辑（隐式体现在新的结构中）。

### 输出格式 (JSON Only)
输出 **纯 JSON**，不要包含 markdown 标记。结构严格如下：

```json
{
  "project_title": "精炼而宏大的标题",
  "author": "Magnum Opus AI",
  "description": "300字以上的项目综述。这部分需包含：1. 本书宗旨与核心论点；2. 针对 Writer 的内容深度要求（如：严格推导、第一性原理）；3. 针对 Designer/Transformer 的技术实现建议（如：SVG 动画实现机制、CSS 特殊效果、交互式 Slide 布局等）。",
  "sections": [
    {
      "id": "sec-1",
      "title": "章节标题",
      "summary": "详细摘要：本章将首先探讨...接着分析...重点解释...最后建立...与下一章的关系是...",
      "estimated_words": 3500
    }
  ],
  "knowledge_map": {
    "sec-1": ["核心概念A", "机制B"],
    "sec-2": ["病理C", "临床表现D"]
  }
}
```
"""


class ArchitectAgent:
    """首席架构师 Agent"""
    
    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()
    
    def run(self, state: AgentState, feedback: Optional[str] = None) -> AgentState:
        """
        执行架构设计
        
        Args:
            state: AgentState
            feedback: 用户反馈（用于修订模式）
            
        Returns:
            更新后的 AgentState
        """
        # 构建提示 (parts)
        parts = self._build_prompt_parts(state, feedback)
        
        # 调用 Gemini
        response = self.client.generate(
            parts=parts,
            system_instruction=ARCHITECT_SYSTEM_PROMPT,
            temperature=0.7, # 稍微增加创造性以获得更好的结构
        )
        
        # 调试日志：保存原始响应
        try:
            log_path = Path(state.workspace_path) / "architect_raw_response.txt"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(response.text, encoding="utf-8")
        except:
            pass

        if not response.success:
            state.errors.append(f"Architect Agent failed: {response.error}")
            return state
        
        # 解析 manifest
        try:
            manifest = self._parse_manifest(response.text)
            state.manifest = manifest
            
            # 保存 manifest 到工作目录
            self._save_manifest(state)
            
        except Exception as e:
            state.errors.append(f"Failed to parse manifest: {str(e)}")
            # 如果解析失败，把解析用的 cleaned content 也存一下方便排查
            try:
                debug_path = Path(state.workspace_path) / "manifest_parse_error_content.txt"
                debug_path.write_text(response.text, encoding="utf-8")
            except:
                pass
        
        return state
    
    def _build_prompt_parts(self, state: AgentState, feedback: Optional[str] = None) -> list[dict]:
        """构建提示部件列表"""
        final_parts = []
        
        # 1. 核心输入：Project Brief (优先) 或 Raw Materials
        if state.project_brief:
            final_parts.append({"text": "# 📋 项目需求书 (Project Brief)\n这是经过确认的详细需求：\n\n" + state.project_brief + "\n\n"})
        else:
            final_parts.append({"text": "# 原始需求\n" + state.raw_materials + "\n\n"})
            
        # 2. 参考资料
        if state.reference_docs:
            ref_text = ["# 📚 参考资料\n"]
            for doc_path in state.reference_docs:
                try:
                    content = Path(doc_path).read_text(encoding="utf-8")
                    ref_text.append(f"## {doc_path}\n{content}\n")
                except Exception:
                    pass
            final_parts.append({"text": "".join(ref_text)})
        
        # 3. 图片素材
        if hasattr(state, "images") and state.images:
            final_parts.extend(state.images)
            final_parts.append({"text": "\n(包含上述视觉参考资料)\n"})

        # 4. 修订模式处理
        if state.manifest:
            current_json = state.manifest.model_dump_json(indent=2)
            revision_context = f"""
# ⚠️ 修订模式 (Revision Mode)

我们已经有了一个初步的 Manifest 设计：
```json
{current_json}
```

"""
            if feedback:
                revision_context += f"""
## 用户反馈 (User Feedback)
用户对上述设计提出了以下修改/完善意见，请务必严格遵守：
> {feedback}

任务：请基于现有 Manifest 和 用户反馈，重新生成一份完善的 Manifest JSON。保持未被批评部分的优点，修正被指出的问题。
"""
            else:
                revision_context += "\n请基于新的理解重新优化这份设计。\n"
                
            final_parts.append({"text": revision_context})
        else:
            final_parts.append({"text": "\n# 任务\n请基于以上所有信息，设计一份 SOTA 级别的 Manifest JSON。\n"})
            
        return final_parts
    
    def _parse_manifest(self, text: str) -> Manifest:
        """解析 Manifest JSON (增强鲁棒性)"""
        # 尝试寻找 JSON 块
        import re
        
        cleaned = text.strip()
        
        # 处理 ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            # 尝试直接寻找第一个 { 和最后一个 }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start:end+1]
        
        data = json.loads(cleaned)
        
        # 转换 sections
        sections = []
        for sec_data in data.get("sections", []):
            sections.append(SectionInfo(
                id=sec_data["id"],
                title=sec_data["title"],
                summary=sec_data.get("summary", ""),
                estimated_words=sec_data.get("estimated_words", 0),
            ))
        
        return Manifest(
            project_title=data.get("project_title", "Untitled"),
            author=data.get("author"),
            description=data.get("description", ""),
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


def create_architect_agent(client: Optional[GeminiClient] = None) -> ArchitectAgent:
    """创建架构师 Agent 实例"""
    return ArchitectAgent(client=client)
