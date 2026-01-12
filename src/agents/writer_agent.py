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

from ..core.gemini_client import GeminiClient, GeminiResponse
from ..core.types import (
    AgentState,
    SectionInfo,
    AssetFulfillmentAction,
    AssetQualityLevel,
)


# ============================================================================
# SOTA 2.0 系统提示词 - Writer-Direct-Inject 协议
# ============================================================================

WRITER_SYSTEM_PROMPT = """你是一位资深技术写手，负责撰写高质量的 Markdown 章节内容。

## 核心职责
1. **深度创作**: 根据项目规划和原始素材，撰写严密的技术内容
2. **图文并茂**: 主动在合适位置插入图像，提升内容的可读性和教学效果
3. **资产决策**: 判断现有资产是否适合使用，不适合则声明需要新资产

## 写作规范

### Markdown 格式
- 使用标准 Markdown 语法
- 数学公式: 行内 `$...$`，块级 `$$...$$`
- 代码块: ```language ... ```
- 内部引用: `[REF:sec-id]` 格式

### 特殊块约定
- **重点卡片**: `:::important` ... `:::` 用于核心概念或公理
- **警告块**: `:::warning` ... `:::` 用于常见陷阱或病理情况
- **提示块**: `:::tip` ... `:::` 用于实用建议

## 🖼️ 图像资产注入协议 (Writer-Direct-Inject)

你将收到一个「可用资产注册表 (UAR)」，其中列出了所有可复用的图像资产及其质量评估。

### 决策流程

当你认为某个位置需要图像时：

**步骤 1: 查看 UAR 是否有匹配的资产**
- 检查语义描述是否符合你的需求
- 检查质量等级 (HIGH/MEDIUM/LOW)
- 检查适用/不适用场景

**步骤 2: 做出决策**

#### 情况 A: 找到合适的高质量资产 → 直接注入 `<img>` 标签

```markdown
这里是正文内容...

<figure>
<img src="assets/images/xxx.png" alt="描述" style="object-position: 50% 50%; object-fit: cover; width: 100%" data-asset-id="资产ID">
<figcaption>图 X: 说明文字</figcaption>
</figure>

继续正文内容...
```

#### 情况 B: 没有合适资产 或 质量不达标 → 使用 `:::visual` 指令

```markdown
这里是正文内容...

:::visual {"id": "s1-fig-xxx", "action": "GENERATE_SVG", "description": "需要展示的内容描述"}
这张图用于说明 XXX 概念，需要清晰展示 A、B、C 三个组件的关系。
:::

继续正文内容...
```

### `:::visual` 指令格式

```json
{
  "id": "章节命名空间-fig-名称",
  "action": "USE_EXISTING | GENERATE_SVG | SEARCH_WEB | GENERATE_MERMAID | SKIP",
  "description": "图像内容描述",
  "matched_asset": "如果曾考虑某资产但被拒绝，填写其 ID",
  "rejection_reason": "拒绝原因（如：分辨率不足、内容不匹配、风格不符）",
  "search_queries": ["搜图关键词1", "关键词2"],  // 仅 SEARCH_WEB 时使用
  "svg_spec": "SVG 规格描述",  // 仅 GENERATE_SVG 时使用
  "mermaid_code": "```mermaid\n...\n```"  // 仅 GENERATE_MERMAID 时使用
}
```

### action 类型说明

| Action | 何时使用 |
|--------|---------|
| `USE_EXISTING` | UAR 中有合适资产，但需要下游处理 |
| `GENERATE_SVG` | 需要精确的示意图、流程图、物理模型图 |
| `SEARCH_WEB` | 需要真实照片、复杂医学图像、实拍图片 |
| `GENERATE_MERMAID` | 需要流程图、序列图、类图等 |
| `SKIP` | 此处不需要图像 |

### 质量判断标准

- **HIGH**: 直接使用，无需犹豫
- **MEDIUM**: 可用，但如果是关键位置建议生成更好的
- **LOW**: 不建议使用，请选择 GENERATE_SVG 或 SEARCH_WEB

## 输出要求

1. **仅输出 Markdown 内容**，不要输出任何元数据或解释
2. **不要在标题中包含章节编号**，组装器会处理
3. **字数匹配**：确保内容长度接近预估字数
4. **语言一致**：使用与项目简报相同的语言
5. **图文并茂**：主动寻找适合插入图像的位置，让内容更加生动

## 重要提醒

- 你可以同时看到原始参考图像和 UAR 中的资产信息
- 如果某张参考图像非常适合，可以直接使用（检查其在 UAR 中的 ID）
- 不要勉强使用不合适的资产，宁可声明需要新资产
- 每个 `:::visual` 指令都要有清晰的 description，便于下游履约
"""


class WriterAgent:
    """
    全量上下文写手 Agent (SOTA 2.0)

    支持：
    - Full-Context Perception: 完整规划 + Brief + 原材料 + UAR + 历史章节
    - Writer-Direct-Inject: 直接注入 `<img>` 标签或声明 :::visual 指令
    - 多模态输入: 文本 + 参考图像
    """

    def __init__(self, client: Optional[GeminiClient] = None):
        self.client = client or GeminiClient()

    async def run(self, state: AgentState) -> AgentState:
        """
        执行章节写作（单个章节）

        注意：此方法每次只写一个章节，需要在工作流中循环调用
        """
        if not state.manifest:
            state.errors.append("Writer Agent: Manifest not available")
            return state

        # SOTA 2.0: 确保 UAR 已初始化
        state.initialize_uar()

        # Check if we are in a REWRITE loop triggered by QA
        if getattr(state, "rewrite_needed", False):
            print(f"  [Writer] 🔄 Rewrite triggered by Critic. Feedback: {getattr(state, 'rewrite_feedback', '')[:100]}...")
            state.current_section_index = 0
            state.completed_md_sections = []
            state.rewrite_needed = False

        # 获取当前要写的章节
        if state.current_section_index >= len(state.manifest.sections):
            return state

        current_section = state.manifest.sections[state.current_section_index]
        namespace = state.get_current_section_namespace()

        print(f"  [Writer] 📝 Writing section {current_section.id} ({namespace})...")

        # SOTA 2.0: 构建多模态提示 (文本 + 图像)
        prompt_parts = self._build_multimodal_prompt(state, current_section, namespace)

        # 调用 Gemini (带重试逻辑)
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                if isinstance(prompt_parts, list):
                    response = await self.client.generate_async(
                        parts=prompt_parts,  # 支持多模态
                        system_instruction=WRITER_SYSTEM_PROMPT,
                        temperature=0.7,
                        stream=True
                    )
                else:
                    response = await self.client.generate_async(
                        prompt=prompt_parts,
                        system_instruction=WRITER_SYSTEM_PROMPT,
                        temperature=0.7,
                        stream=True
                    )
                if response.success:
                    break
                else:
                    print(f"  [Writer] Attempt {attempt+1} failed: {response.error}")
            except Exception as e:
                print(f"  [Writer] Attempt {attempt+1} error: {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2 * (attempt + 1))

        if not response or not response.success:
            state.errors.append(f"Writer Agent failed on {current_section.id} after {max_retries} attempts. Last error: {response.error if response else 'Unknown'}")
            return state

        # 保存章节
        try:
            section_path = self._save_section(state, current_section, response.text)
            current_section.file_path = str(section_path)
            state.completed_md_sections.append(str(section_path))
            state.current_section_index += 1
            print(f"  [Writer] ✓ Section {current_section.id} saved to {section_path}")
        except Exception as e:
            state.errors.append(f"Failed to save section {current_section.id}: {str(e)}")

        return state
    
    async def run_all(self, state: AgentState) -> AgentState:
        """写作所有章节（循环调用 run）"""
        while not state.all_sections_written():
            state = await self.run(state)
            if state.errors:
                break
        return state

    def _build_multimodal_prompt(
        self,
        state: AgentState,
        section: SectionInfo,
        namespace: str
    ) -> Union[str, list]:
        """
        构建多模态提示 (SOTA 2.0 Full-Context Perception)

        返回:
            - 如果有图像: 返回 list[dict] (多模态格式)
            - 如果无图像: 返回 str (纯文本格式)
        """
        text_parts = []

        # ================================================================
        # 0. Critic Feedback (if in rewrite loop)
        # ================================================================
        rewrite_feedback = getattr(state, "rewrite_feedback", None)
        if rewrite_feedback:
            text_parts.append("# ⚠️ 审核反馈 (必须解决以下问题)\n")
            text_parts.append(f"上一版草稿被退回，原因如下：\n{rewrite_feedback}\n\n")

        # ================================================================
        # 1. 项目概览
        # ================================================================
        text_parts.append("# 📋 项目概览\n")
        text_parts.append(f"**标题**: {state.manifest.project_title}\n")
        text_parts.append(f"**描述**: {state.manifest.description}\n\n")

        # ================================================================
        # 2. 项目简报 (Brief)
        # ================================================================
        if state.project_brief:
            text_parts.append("# 📝 项目简报\n")
            text_parts.append(f"{state.project_brief}\n\n")

        # ================================================================
        # 3. 完整目录与进度
        # ================================================================
        text_parts.append("# 📚 文章目录\n")
        for i, sec in enumerate(state.manifest.sections):
            marker = "👉 **当前**" if sec.id == section.id else "  "
            status = "✅" if sec.file_path else "⏳"
            ns = f"s{i+1}"
            text_parts.append(f"{marker} [{status}] {sec.id} ({ns}): {sec.title}\n")
        text_parts.append("\n")

        # ================================================================
        # 4. SOTA 2.0: 可用资产注册表 (UAR)
        # ================================================================
        if state.asset_registry:
            text_parts.append(state.asset_registry.to_summary())
            text_parts.append("\n\n")

        # ================================================================
        # 5. 已完成章节的完整内容
        # ================================================================
        if state.completed_md_sections:
            text_parts.append("# ✍️ 已完成章节\n")
            text_parts.append("*请确保与前序章节的术语、风格保持一致*\n\n")
            for md_path in state.completed_md_sections:
                try:
                    content = Path(md_path).read_text(encoding="utf-8")
                    # Full content - no truncation (Gemini 1M context)
                    text_parts.append(f"\n---\n{content}\n")
                except Exception:
                    text_parts.append(f"\n[读取失败: {md_path}]\n")

        # ================================================================
        # 6. 原始素材参考
        # ================================================================
        text_parts.append("\n# 📚 原始素材参考\n")
        text_parts.append("*以下是用户提供的原始资料，请基于这些内容进行创作*\n\n")
        text_parts.append(state.raw_materials)
        text_parts.append("\n")

        # ================================================================
        # 7. 当前章节任务
        # ================================================================
        text_parts.append(f"\n# 🎯 当前任务：撰写 {section.id} (命名空间: {namespace})\n")
        text_parts.append(f"**章节标题**: {section.title}\n")
        text_parts.append(f"**章节摘要**: {section.summary}\n")
        text_parts.append(f"**⚠️ 最低字数要求**: {section.estimated_words} 字 (这是硬性要求，必须达到！)\n")
        text_parts.append(f"""
:::warning
**字数要求**: 本章节必须达到 **{section.estimated_words}** 字以上！
- 中文字符数（不含标点和空格）必须达到此数字
- 内容不足将被退回重写
- 请确保内容充实、论证详细、示例丰富
:::
""")

        # 知识点
        if section.id in state.manifest.knowledge_map:
            points = state.manifest.knowledge_map[section.id]
            text_parts.append(f"**核心知识点**: {', '.join(points)}\n")

        # 章节元数据
        if hasattr(section, 'metadata') and section.metadata:
            text_parts.append(f"\n**章节元数据 (设计意图)**:\n")
            for k, v in section.metadata.items():
                text_parts.append(f"- {k}: {v}\n")
            text_parts.append("\n")

        # ================================================================
        # 8. 图像资产使用指导
        # ================================================================
        text_parts.append("\n# 🖼️ 图像资产使用指导\n")
        text_parts.append(f""")

请在合适的位置插入图像，遵循以下规则：

1. **直接使用 UAR 资产**: 如果上面的 UAR 中有合适的资产，直接写 `<img>` 标签
   - 格式: `<img src="路径" alt="描述" style="object-position: 50% 50%; object-fit: cover" data-asset-id="资产ID">`

2. **声明新资产需求**: 如果没有合适资产或质量不达标，使用 `:::visual` 指令
   - 所有新资产 ID 必须以 `{namespace}-` 开头，例如 `{namespace}-fig-xxx`

3. **下方有参考图像**: 如果你看到参考图像，请判断是否适合直接使用（检查 UAR 中的对应条目）

请开始撰写这个章节的完整 Markdown 内容。
""")

        # ================================================================
        # 构建最终输出 (支持多模态)
        # ================================================================
        text_content = "".join(text_parts)

        # 如果有图像素材，构建多模态请求
        if state.images:
            multimodal_parts = [{"text": text_content}]

            # 添加参考图像
            multimodal_parts.append({"text": "\n\n# 📷 参考图像\n*以下是用户提供的参考图像，请判断是否适合使用*\n\n"})
            for i, img in enumerate(state.images):
                multimodal_parts.append(img)  # 直接添加图像 dict
                multimodal_parts.append({"text": f"\n*(参考图 {i+1})*\n\n"})

            return multimodal_parts

        return text_content

    def _build_prompt(self, state: AgentState, section: SectionInfo) -> str:
        """
        构建纯文本提示 (兼容旧版调用)

        DEPRECATED: 请使用 _build_multimodal_prompt
        """
        namespace = f"s{state.current_section_index + 1}"
        result = self._build_multimodal_prompt(state, section, namespace)
        if isinstance(result, list):
            # 提取文本部分
            return "".join([p.get("text", "") for p in result if isinstance(p, dict) and "text" in p])
        return result
    
    def _save_section(self, state: AgentState, section: SectionInfo, content: str) -> Path:
        """保存章节到工作目录"""
        md_dir = Path(state.workspace_path) / "md"
        md_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用章节 ID 作为文件名
        file_path = md_dir / f"{section.id}.md"
        
        # 添加章节标题
        full_content = f"# {section.title}\n\n{content}"
        file_path.write_text(full_content, encoding="utf-8")
        
        return file_path


def create_writer_agent(client: Optional[GeminiClient] = None) -> WriterAgent:
    """创建写手 Agent 实例"""
    return WriterAgent(client=client)