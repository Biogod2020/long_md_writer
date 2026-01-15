"""
AssetFulfillmentAgent: SOTA 2.0 Phase D 资产履约器

核心职责：
1. 解析 Writer 输出中的 :::visual 指令块
2. 根据 action 类型执行资产生成/搜索
3. 使用 VLM 计算智能焦点 (crop_metadata)
4. 注册新资产到 UAR
5. 将 :::visual 块替换为实际的 <img> 或其他内容

执行时机：
- 在 Writer 完成每个章节后执行
- 在 HTML 转换前完成所有资产履约
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Optional

from ...core.gemini_client import GeminiClient
from ...core.types import (
    AgentState,
    AssetEntry,
    AssetSource,
    AssetFulfillmentAction,
)
from .models import VisualDirective
from .processors.svg import generate_svg, generate_svg_async
from .processors.mermaid import generate_mermaid, generate_mermaid_async
from .processors.focus import compute_focus, compute_focus_async
from .utils import (
    generate_figure_html,
    generate_placeholder_html,
    generate_mermaid_html,
    resolve_asset_path,
)


class AssetFulfillmentAgent:
    """
    资产履约 Agent

    负责处理 Writer 输出中的 :::visual 指令，生成或搜索资产
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        output_dir: str = "generated_assets",
        skip_generation: bool = False,
        skip_search: bool = False
    ):
        """
        初始化资产履约器

        Args:
            client: Gemini API 客户端
            output_dir: 生成资产的输出目录
            skip_generation: 跳过 SVG/Mermaid 生成 (用于测试)
            skip_search: 跳过网络搜索 (用于测试)
        """
        self.client = client or GeminiClient()
        self.output_dir = output_dir
        self.skip_generation = skip_generation
        self.skip_search = skip_search

    async def run_async(self, state: AgentState, section_content: str, namespace: str) -> tuple[AgentState, str]:
        """
        异步执行资产履约

        Args:
            state: Agent 状态
            section_content: Writer 输出的章节内容
            namespace: 当前章节的命名空间

        Returns:
            (更新后的状态, 履约后的内容)
        """
        print(f"[AssetFulfillment] 开始处理章节资产 (namespace: {namespace})")

        # 确保 UAR 已初始化
        uar = state.get_uar()

        # 确保输出目录存在
        workspace_path = Path(state.workspace_path)
        output_path = workspace_path / self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # 解析所有 :::visual 指令
        directives = self._parse_visual_directives(section_content)
        print(f"[AssetFulfillment] 发现 {len(directives)} 个 :::visual 指令")

        if not directives:
            return state, section_content

        # 逐个履约
        fulfilled_content = section_content
        offset = 0

        for directive in directives:
            try:
                # 异步执行履约
                result = await self._fulfill_directive_async(directive, uar, output_path, namespace, workspace_path)

                if result.fulfilled and result.result_html:
                    adjusted_start = result.start_pos + offset
                    adjusted_end = result.end_pos + offset

                    fulfilled_content = (
                        fulfilled_content[:adjusted_start] +
                        result.result_html +
                        fulfilled_content[adjusted_end:]
                    )

                    offset += len(result.result_html) - (result.end_pos - result.start_pos)

                    if result.result_asset_id:
                        print(f"  ✓ {result.id} -> {result.result_asset_id}")
                else:
                    print(f"  ⚠ {result.id}: {result.error or '履约失败'}")
                    state.errors.append(f"AssetFulfillment: {result.id} - {result.error}")

            except Exception as e:
                print(f"  ✗ {directive.id}: {e}")
                state.errors.append(f"AssetFulfillment: {directive.id} - {e}")

        return state, fulfilled_content

    def _parse_visual_directives(self, content: str, context_chars: int = 500) -> list[VisualDirective]:
        """
        解析内容中的所有 :::visual 指令块，并提取上下文

        Args:
            content: 章节的完整 Markdown 内容
            context_chars: 上下文提取的字符数 (默认 500)
        """
        directives = []
        pattern = r':::visual[^\n]*\n[\s\S]*?:::'

        for match in re.finditer(pattern, content):
            raw_block = match.group(0)
            lines = raw_block.splitlines()
            header_line = lines[0].strip()
            body_content = "\n".join(lines[1:-1]).strip()
            json_config = header_line[len(":::visual"):].strip()

            # 提取上下文 (Sliding Context)
            start_pos = match.start()
            end_pos = match.end()
            context_start = max(0, start_pos - context_chars)
            context_end = min(len(content), end_pos + context_chars)
            context_before = content[context_start:start_pos].strip()
            context_after = content[end_pos:context_end].strip()

            directive = VisualDirective(
                raw_block=raw_block,
                start_pos=start_pos,
                end_pos=end_pos,
                context_before=context_before,
                context_after=context_after,
            )

            try:
                config = json.loads(json_config) if json_config else {}
                directive.id = config.get("id", f"visual-{len(directives)}")

                action_str = config.get("action", "GENERATE_SVG").upper()
                directive.action = {
                    "GENERATE_SVG": AssetFulfillmentAction.GENERATE_SVG,
                    "SEARCH_WEB": AssetFulfillmentAction.SEARCH_WEB,
                    "GENERATE_MERMAID": AssetFulfillmentAction.GENERATE_MERMAID,
                    "USE_EXISTING": AssetFulfillmentAction.USE_EXISTING,
                    "SKIP": AssetFulfillmentAction.SKIP,
                }.get(action_str, AssetFulfillmentAction.GENERATE_SVG)

                directive.description = config.get("description", body_content)
                directive.focus = config.get("focus")
                directive.style_hints = config.get("style_hints")
                directive.matched_asset_id = config.get("matched_asset_id") or config.get("matched_asset")

            except json.JSONDecodeError as e:
                directive.error = f"JSON 解析失败: {e}"
                directive.description = body_content

            if not directive.description:
                directive.description = body_content

            directives.append(directive)

        return directives

    async def _fulfill_directive_async(
        self,
        directive: VisualDirective,
        uar,
        output_path: Path,
        namespace: str,
        workspace_path: Path
    ) -> VisualDirective:
        """异步履约单个指令"""
        if directive.action == AssetFulfillmentAction.SKIP:
            directive.fulfilled = True
            directive.result_html = f"<!-- SKIPPED: {directive.id} -->"
            return directive

        if directive.action == AssetFulfillmentAction.USE_EXISTING:
            return await self._fulfill_use_existing_async(directive, uar, namespace, workspace_path)

        if directive.action == AssetFulfillmentAction.GENERATE_SVG:
            return await self._fulfill_generate_svg_async(directive, uar, output_path, namespace, workspace_path)

        if directive.action == AssetFulfillmentAction.GENERATE_MERMAID:
            return await self._fulfill_generate_mermaid_async(directive, namespace)

        if directive.action == AssetFulfillmentAction.SEARCH_WEB:
            return self._fulfill_search_web(directive, uar, output_path, namespace)

        directive.error = f"未知的 action 类型: {directive.action}"
        return directive

    async def _fulfill_use_existing_async(
        self,
        directive: VisualDirective,
        uar,
        namespace: str = "",
        workspace_path: Optional[Path] = None
    ) -> VisualDirective:
        """异步使用现有资产（支持上下文增强的焦点计算）"""
        asset_id = directive.matched_asset_id
        if not asset_id or asset_id not in uar.assets:
            directive.error = f"未找到资产: {asset_id}"
            return directive

        asset = uar.assets[asset_id]
        asset.increment_usage(namespace or "unknown")

        if directive.focus and workspace_path and not self.skip_generation:
            full_path = resolve_asset_path(asset, workspace_path)
            if full_path:
                # 结合上下文构建更丰富的焦点描述
                focus_with_context = directive.focus
                if directive.context_before or directive.context_after:
                    focus_with_context = f"{directive.focus}\n\n[Surrounding Context]\n{directive.context_before[:200]}...{directive.context_after[:200]}"
                crop = await compute_focus_async(self.client, full_path, focus_with_context)
                if crop:
                    asset.crop_metadata = crop
                    uar.register_immediate(asset)

        directive.fulfilled = True
        directive.result_asset_id = asset_id
        directive.result_html = generate_figure_html(asset, directive.description)

        return directive

    async def _fulfill_generate_svg_async(
        self,
        directive: VisualDirective,
        uar,
        output_path: Path,
        namespace: str,
        workspace_path: Path
    ) -> VisualDirective:
        """异步生成 SVG 图形（带上下文感知）"""
        if self.skip_generation:
            directive.fulfilled = True
            directive.result_html = generate_placeholder_html(directive.id, directive.description, "svg")
            return directive

        # 使用包含上下文的完整描述，提升生成质量
        full_context = directive.get_full_context()
        svg_code = await generate_svg_async(self.client, full_context, directive.style_hints or "")
        if not svg_code:
            directive.error = "未能生成 SVG 代码"
            return directive

        filename = f"{directive.id}.svg"
        svg_path = output_path / filename
        svg_path.write_text(svg_code, encoding="utf-8")

        content_hash = hashlib.md5(svg_code.encode()).hexdigest()
        try:
            relative_path = svg_path.relative_to(workspace_path)
        except ValueError:
            relative_path = svg_path

        asset_entry = AssetEntry(
            id=directive.id,
            source=AssetSource.AI,
            local_path=str(relative_path),
            semantic_label=directive.description[:100],
            content_hash=content_hash,
            alt_text=directive.description,
            tags=["svg", "generated", namespace],
        )
        asset_entry.increment_usage(namespace or "unknown")
        uar.register_immediate(asset_entry)

        directive.fulfilled = True
        directive.result_asset_id = directive.id
        directive.result_html = generate_figure_html(asset_entry, directive.description)

        return directive

    async def _fulfill_generate_mermaid_async(self, directive: VisualDirective, namespace: str) -> VisualDirective:
        """异步生成 Mermaid 图表（带上下文感知）"""
        if self.skip_generation:
            directive.fulfilled = True
            placeholder_mermaid = "graph TD\n    A[占位符] --> B[内容]"
            directive.result_html = generate_mermaid_html(placeholder_mermaid, directive.description)
            return directive

        # 使用包含上下文的完整描述
        full_context = directive.get_full_context()
        mermaid_code = await generate_mermaid_async(self.client, full_context, directive.style_hints or "")
        if not mermaid_code:
            directive.error = "未能生成 Mermaid 代码"
            return directive

        directive.fulfilled = True
        directive.result_html = generate_mermaid_html(mermaid_code, directive.description)
        return directive

    def _fulfill_search_web(self, directive: VisualDirective, uar, output_path: Path, namespace: str) -> VisualDirective:
        """搜索网络图片"""
        if self.skip_search:
            directive.fulfilled = True
            directive.result_html = generate_placeholder_html(directive.id, directive.description, "web-image")
            return directive

        directive.error = "网络搜索功能尚未实现"
        return directive

    async def _calculate_reuse_score(self, intent: str, asset: AssetEntry) -> int:
        """
        使用 LLM 计算现有资产与新意图之间的语义匹配得分 (0-100)
        """
        prompt = f"""请评估以下“视觉意图”与“现有资产”之间的匹配程度。

### 视觉意图 (需求)
{intent}

### 现有资产 (已有)
- ID: {asset.id}
- 语义标签: {asset.semantic_label}
- 标签: {", ".join(asset.tags)}

### 评分标准
- 100: 完全匹配，可以直接复用。
- 90-99: 极度匹配，虽然描述略有差异但核心视觉内容一致。
- 70-89: 部分匹配，可以复用但可能不是最佳选择。
- 0-69: 不匹配，建议重新生成或搜索。

请以 JSON 格式输出评分结果：
```json
{{
  "score": 0-100,
  "reason": "评分理由简述"
}}
```
"""
        try:
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一位专业的视觉资产评估专家。请客观评估资产复用得分。",
                temperature=0.0
            )
            
            if response.success:
                # 尝试解析 JSON
                match = re.search(r'\{[\s\S]*\}', response.text)
                if match:
                    data = json.loads(match.group())
                    return int(data.get("score", 0))
            
            return 0
        except Exception as e:
            print(f"  [AssetFulfillment] 评分出错: {e}")
            return 0

    def _query_uar_for_candidates(self, uar, limit: int = 10) -> list[AssetEntry]:
        """
        从 UAR 中获取可复用的候选资产
        """
        return uar.get_reusable_assets()[:limit]
