"""
Node 2: Content Writer Agent (全量上下文写手) - SOTA 2.0

采用全量输入模式 (Full-Context Perception)，支持：
- 统一资产注册表 (UAR) 查询与直接注入
- 资产质量判断与拒绝
- 多模态输入（文本 + 图像）
"""

import asyncio
from pathlib import Path
from typing import Optional, Union

from ..core.gemini_client import GeminiClient
from ..core.types import (
    AgentState,
    SectionInfo,
)


# ============================================================================
# SOTA 2.0 系统提示词 - Writer-Direct-Inject 协议
# ============================================================================

WRITER_SYSTEM_PROMPT = """你是一位专业的学术与技术作者，负责根据上游规划撰写准确、详实且易于理解的 Markdown 章节内容。

## 核心职责
1. **指令驱动写作**: 严格遵循项目简报（Brief）和架构师清单（Manifest）中的要求，确保内容逻辑与规划高度统一。
2. **风格动态适配**: 仔细解析 Manifest 中的 `aesthetic_intent` 和章节 `metadata`，据此调整文案的语调（如专业、通俗或叙事）及视觉描述风格。
3. **视觉意图整合**: 在文稿中合适位置插入图像指令，通过视觉辅助精准传达核心概念。
4. **资产理性决策**: 基于 UAR 注册表判断现有资产的可用性，决定是复用、更新还是生成新资产。

## 写作规范

### Markdown 格式
- 使用标准 Markdown 语法。
- 数学公式: 行内 `$...$`，块级 `$$...$$`。
- 内部引用: `[REF:sec-id]`。

### 语义容器
- 根据内容需要，可选择性使用 `:::important` (核心概念), `:::warning` (陷阱风险), `:::tip` (实践建议) 等容器。

### 🖼️ 图像资产指令协议 (Visual Directive Protocol)

### 🛑 严禁项
1. **严禁直接书写 `<img>` 或 `<figure>` 标签**：所有图像需求必须通过 `:::visual` 指令声明。
2. **严禁注入未经证实的外部链接**。
3. **严禁在指令块外描述图像细节**。

### 🚀 媒介匹配智慧 (Media Alignment Intelligence)
请根据内容本质选择最精准的媒介，以下是我提供的参考意见，请你结合具体情况理性地选择：
- **SVG (物理与几何)**: 用于不需要过多真实细节的示意图。
- **MERMAID (抽象逻辑)**: 仅用于表达高度抽象的概念流/决策。
- **SEARCH (真实世界)**: 用于获取真实的图像+需要真实高清细节的图像。

### ✅ 视觉指令生成准则
当你认为需要配图时，必须提供专业且具体的描述 (Description)。描述应遵循 **[核心主体] + [细节特征] + [专业要求]** 的逻辑。
**注意：风格描述必须参考 Architect 提供的视觉要求（如配色方案、材质建议）。**

- **SVG (逻辑/模型)**: 描述图形的几何构成、标注内容，并指明如何应用 TechSpec 中的配色。
- **SEARCH (实拍/插图)**: 描述所需画面的主体、媒介类型及关键视觉特征。
- **MERMAID (流程/关系)**: 描述逻辑节点的层级、流向及分支。

### 决策示范

#### 情况 A: 复用 UAR 资产
```markdown
:::visual {"id": "章节命名空间-fig-名称", "action": "USE_EXISTING", "matched_asset": "u-img-xxx", "reuse_score": 95, "reason": "该资产展示的结构与本段描述的逻辑高度契合", "description": "对该资产视觉特征的客观描述"}
在此处结合资产的视觉细节进行深度文字解读。
:::
```

#### 情况 B: 生成新资产
```markdown
:::visual {"id": "章节命名空间-fig-名称", "action": "GENERATE_SVG", "reason": "此处概念较为抽象，需要通过几何模型直观展示其物理本质", "description": "核心主体：[详细描述]；特征：[标注与细节]；风格：[参考 Architect 要求的配色与布局约束]"}
此处补充详细的意图说明，确保下游 Agent 产出准确、清晰的画面。
:::
```

### `:::visual` 指令 JSON 格式
```json
{
  "id": "章节命名空间-fig-名称",
  "action": "USE_EXISTING | GENERATE_SVG | SEARCH_WEB | GENERATE_MERMAID",
  "reason": "强制要求：解释选择/生成该图像的逻辑必要性",
  "description": "具体的图像描述，需包含内容、细节及与 Architect 要求相符的风格建议",
  "matched_asset": "仅 USE_EXISTING 时填写 UAR ID",
  "reuse_score": 0-100, 
  "search_queries": ["搜图关键词"] 
}
```

## 输出要求
1. **仅输出 Markdown 内容**，不包含元数据或额外解释。
2. **内容厚度**: 确保论证严密、示例丰富，字数应接近或超过建议篇幅。
3. **逻辑一致性**: 确保专业术语和叙事风格在全书范围内保持一致。
"""


class WriterAgent:
    """
    全量上下文写手 Agent (SOTA 2.0)

    支持：
    - Full-Context Perception: 完整规划 + Brief + 原材料 + UAR + 历史章节
    - Writer-Direct-Inject: 声明 :::visual 指令
    - 多模态输入: 文本 + 参考图像
    """

    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()

    async def run(self, state: AgentState) -> AgentState:
        """执行章节写作（单个章节）"""
        if not state.manifest:
            state.errors.append("Writer Agent: Manifest not available")
            return state

        # 确保 UAR 已初始化
        state.initialize_uar()

        # 处理审核退回的重写逻辑
        if getattr(state, "rewrite_needed", False):
            print(f"  [Writer] 🔄 Rewrite triggered by Critic. Feedback: {getattr(state, 'rewrite_feedback', '')[:100]}...")
            state.current_section_index = 0
            state.completed_md_sections = []
            state.rewrite_needed = False

        if state.current_section_index >= len(state.manifest.sections):
            return state

        current_section = state.manifest.sections[state.current_section_index]
        namespace = state.get_current_section_namespace()

        print(f"  [Writer] 📝 Writing section {current_section.id} ({namespace})...")

        # 构建多模态提示
        prompt_parts = self._build_multimodal_prompt(state, current_section, namespace)

        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = await self.client.generate_async(
                    parts=prompt_parts if isinstance(prompt_parts, list) else None,
                    prompt=prompt_parts if isinstance(prompt_parts, str) else None,
                    system_instruction=WRITER_SYSTEM_PROMPT,
                    temperature=0.7,
                    stream=True
                )
                if response.success: break
                else: print(f"  [Writer] Attempt {attempt+1} failed: {response.error}")
            except Exception as e: print(f"  [Writer] Attempt {attempt+1} error: {e}")

            if attempt < max_retries - 1: await asyncio.sleep(2 * (attempt + 1))

        if not response or not response.success:
            state.errors.append(f"Writer Agent failed on {current_section.id}. Last error: {response.error if response else 'Unknown'}")
            return state

        if response.thoughts: state.thoughts = response.thoughts

        try:
            section_path = self._save_section(state, current_section, response.text)
            current_section.file_path = str(section_path)
            state.completed_md_sections.append(str(section_path))
            state.current_section_index += 1
            print(f"  [Writer] ✓ Section {current_section.id} saved to {section_path}")
        except Exception as e: state.errors.append(f"Failed to save section {current_section.id}: {str(e)}")

        return state
    
    async def run_all(self, state: AgentState) -> AgentState:
        """写作所有章节"""
        while not state.all_sections_written():
            state = await self.run(state)
            if state.errors: break
        return state

    def _build_multimodal_prompt(
        self,
        state: AgentState,
        section: SectionInfo,
        namespace: str
    ) -> Union[str, list]:
        """构建多模态提示 (SOTA 2.0 Full-Context Perception)"""
        text_parts = []

        # 0. 审核反馈
        rewrite_feedback = getattr(state, "rewrite_feedback", None)
        if rewrite_feedback:
            text_parts.append("# ⚠️ 审核反馈 (必须解决以下问题)\n")
            text_parts.append(f"上一版草稿被退回，原因如下：\n{rewrite_feedback}\n\n")

        # 1. 项目概览
        text_parts.append("# 📋 项目概览\n")
        text_parts.append(f"**标题**: {state.manifest.project_title}\n")
        text_parts.append(f"**描述**: {state.manifest.description}\n\n")

        # 2. 项目简报 (Brief)
        if state.project_brief:
            text_parts.append("# 📝 项目简报 (核心参考)\n")
            text_parts.append(f"{state.project_brief}\n\n")

        # 3. 完整目录与进度
        text_parts.append("# 📚 文章目录与规划\n")
        for i, sec in enumerate(state.manifest.sections):
            marker = "👉 **当前章节**" if sec.id == section.id else "  "
            status = "✅" if sec.file_path else "⏳"
            ns = f"s{i+1}"
            text_parts.append(f"{marker} [{status}] {sec.id} ({ns}): {sec.title}\n")
        text_parts.append("\n")

        # 4. SOTA 2.0: 可用资产注册表 (UAR)
        if state.asset_registry:
            text_parts.append(state.asset_registry.to_summary())
            text_parts.append("\n\n")

        # 5. 已完成章节的完整内容
        if state.completed_md_sections:
            text_parts.append("# ✍️ 已完成章节内容\n")
            text_parts.append("*请确保本章与前序章节的术语使用、叙事风格及质量标准保持高度一致*\n\n")
            for md_path in state.completed_md_sections:
                try:
                    content = Path(md_path).read_text(encoding="utf-8")
                    text_parts.append(f"\n---\n{content}\n")
                except Exception: text_parts.append(f"\n[读取失败: {md_path}]\n")

        # 6. 用户意向与参考资料
        text_parts.append("\n# 🎯 核心创作意向\n")
        text_parts.append(state.user_intent)
        text_parts.append("\n")

        if state.reference_materials:
            text_parts.append("\n# 📚 参考背景资料\n")
            text_parts.append(state.reference_materials)
            text_parts.append("\n")

        # 7. 当前章节具体任务
        text_parts.append(f"\n# 🎯 当前撰写任务：{section.id} (命名空间: {namespace})\n")
        text_parts.append(f"**章节标题**: {section.title}\n")
        text_parts.append(f"**章节摘要**: {section.summary}\n")
        text_parts.append(f"**建议篇幅**: 约 {section.estimated_words} 字以上\n")
        
        # 章节设计意图 (元数据)
        if hasattr(section, 'metadata') and section.metadata:
            text_parts.append("\n**章节设计约束 (Metadata)**:\n")
            for k, v in section.metadata.items(): text_parts.append(f"- {k}: {v}\n")
            text_parts.append("\n")

        # 8. 图像资产使用指导
        text_parts.append("\n# 🖼️ 视觉资产指导\n")
        assigned_ids = section.metadata.get("assigned_assets", [])
        assigned_assets = []
        if assigned_ids and state.asset_registry:
            for aid in assigned_ids:
                asset = state.asset_registry.get_asset(aid)
                if asset: assigned_assets.append(asset)

        if assigned_assets:
            text_parts.append("\n## 🎯 本章分配资产\n")
            text_parts.append("以下资产已预先分配给本章。你**必须**在文中引用它们，并根据视觉细节进行深度解读：\n\n")
            for a in assigned_assets: text_parts.append(f"- **[{a.id}]**: {a.semantic_label}\n")
            text_parts.append("\n")

        text_parts.append(f"""
请在合适的位置插入 `:::visual` 指令，遵循以下规则：
1. **命名规范**: 新资产 ID 必须以 `{namespace}-` 开头。
2. **逻辑支撑 (Reason)**: 对于每一个指令，必须在 JSON 中输出 `reason` 字段，解释其如何支撑当前正文逻辑。
3. **风格对齐**: 仔细阅读项目描述中的视觉设计要求（配色、材质等），并将其融入到 `description` 中。

请开始撰写。
""")

        text_content = "".join(text_parts)
        multimodal_parts = [{"text": text_content}]

        if assigned_assets:
            multimodal_parts.append({"text": "\n\n# 🖼️ 分配资产的视觉细节 (请看图写作)\n"})
            for a in assigned_assets:
                if a.base64_data:
                    multimodal_parts.append({"inline_data": {"mime_type": "image/png", "data": a.base64_data}})
                    multimodal_parts.append({"text": f"\n*(资产: {a.id})*\n\n"})

        if state.images:
            multimodal_parts.append({"text": "\n\n# 📷 参考图像\n"})
            for i, img in enumerate(state.images):
                multimodal_parts.append(img)
                multimodal_parts.append({"text": f"\n*(参考图 {i+1})*\n\n"})

        return multimodal_parts if len(multimodal_parts) > 1 else text_content

    def _build_prompt(self, state: AgentState, section: SectionInfo) -> str:
        namespace = f"s{state.current_section_index + 1}"
        result = self._build_multimodal_prompt(state, section, namespace)
        if isinstance(result, list):
            return "".join([p.get("text", "") for p in result if isinstance(p, dict) and "text" in p])
        return result
    
    def _save_section(self, state: AgentState, section: SectionInfo, content: str) -> Path:
        md_dir = Path(state.workspace_path) / "md"
        md_dir.mkdir(parents=True, exist_ok=True)
        file_path = md_dir / f"{section.id}.md"
        full_content = f"# {section.title}\n\n{content}"
        file_path.write_text(full_content, encoding="utf-8")
        return file_path


def create_writer_agent(client: Optional[GeminiClient] = None) -> WriterAgent:
    """创建写手 Agent 实例"""
    return WriterAgent(client=client)