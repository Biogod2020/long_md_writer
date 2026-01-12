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
from dataclasses import dataclass, field

from ..core.gemini_client import GeminiClient
from ..core.types import (
    AgentState,
    AssetEntry,
    AssetSource,
    AssetVQAStatus,
    AssetQualityLevel,
    AssetFulfillmentAction,
    ReusePolicy,
    CropMetadata,
)


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class VisualDirective:
    """解析后的 :::visual 指令"""
    raw_block: str  # 原始文本块
    start_pos: int  # 在原文中的起始位置
    end_pos: int    # 在原文中的结束位置

    # 从 JSON 配置解析的字段
    id: str = ""
    action: AssetFulfillmentAction = AssetFulfillmentAction.GENERATE_SVG
    description: str = ""
    focus: Optional[str] = None
    style_hints: Optional[str] = None
    matched_asset_id: Optional[str] = None

    # 履约结果
    fulfilled: bool = False
    result_asset_id: Optional[str] = None
    result_html: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# SVG 生成提示词
# ============================================================================

SVG_GENERATION_PROMPT = """你是一个专业的 SVG 矢量图形设计师。请根据以下描述生成一个教育性质的 SVG 图形。

## 描述
{description}

## 风格要求
- 简洁清晰，适合教学用途
- 使用柔和的配色方案
- 包含必要的标注和文字说明
- 图形大小建议: 800x600 或适合内容的尺寸

{style_hints}

## 输出格式
请直接输出完整的 SVG 代码，不要包含任何解释文字。SVG 必须是有效的 XML 格式。

```svg
<svg xmlns="http://www.w3.org/2000/svg" ...>
  ...
</svg>
```
"""

# ============================================================================
# Mermaid 生成提示词
# ============================================================================

MERMAID_GENERATION_PROMPT = """你是一个 Mermaid 图表专家。请根据以下描述生成一个 Mermaid 图表。

## 描述
{description}

## 风格要求
- 结构清晰，层次分明
- 使用恰当的图表类型（flowchart, sequence, class, state 等）
- 标签简洁明了

{style_hints}

## 输出格式
请直接输出 Mermaid 代码，不要包含任何解释文字。

```mermaid
...
```
"""

# ============================================================================
# 焦点计算提示词
# ============================================================================

FOCUS_CALCULATION_PROMPT = """分析这张图片，找到以下描述对应的视觉焦点位置：

焦点描述: {focus_description}

请返回焦点的百分比坐标，格式如下：
```json
{{
  "left": "50%",
  "top": "50%",
  "zoom": 1.0,
  "reasoning": "简短解释为什么选择这个位置"
}}
```

注意：
- left 是水平位置，0% 表示最左边，100% 表示最右边
- top 是垂直位置，0% 表示最上边，100% 表示最下边
- zoom 是缩放因子，1.0 表示不缩放，>1 表示放大
"""


# ============================================================================
# AssetFulfillmentAgent
# ============================================================================

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
        异步执行资产履约 (推荐在异步上下文中使用)

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

    def run(self, state: AgentState, section_content: str, namespace: str) -> tuple[AgentState, str]:
        """
        同步执行资产履约 (仅在非异步上下文中使用)

        Args:
            state: Agent 状态
            section_content: Writer 输出的章节内容
            namespace: 当前章节的命名空间

        Returns:
            (更新后的状态, 履约后的内容)
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 已在异步上下文中，使用同步版本的逻辑
            return self._run_sync(state, section_content, namespace)
        except RuntimeError:
            # 没有运行中的事件循环，可以使用 asyncio.run
            return asyncio.run(self.run_async(state, section_content, namespace))

    def _run_sync(self, state: AgentState, section_content: str, namespace: str) -> tuple[AgentState, str]:
        """同步版本的履约逻辑 (跳过需要 API 调用的生成)"""
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
        offset = 0  # 跟踪替换导致的位置偏移

        for directive in directives:
            try:
                # 执行履约
                result = self._fulfill_directive(directive, uar, output_path, namespace, workspace_path)

                if result.fulfilled and result.result_html:
                    # 替换原始指令块
                    adjusted_start = result.start_pos + offset
                    adjusted_end = result.end_pos + offset

                    fulfilled_content = (
                        fulfilled_content[:adjusted_start] +
                        result.result_html +
                        fulfilled_content[adjusted_end:]
                    )

                    # 更新偏移量
                    offset += len(result.result_html) - (result.end_pos - result.start_pos)

                    # 注册新资产
                    if result.result_asset_id:
                        print(f"  ✓ {result.id} -> {result.result_asset_id}")
                else:
                    print(f"  ⚠ {result.id}: {result.error or '履约失败'}")
                    state.errors.append(f"AssetFulfillment: {result.id} - {result.error}")

            except Exception as e:
                print(f"  ✗ {directive.id}: {e}")
                state.errors.append(f"AssetFulfillment: {directive.id} - {e}")

        return state, fulfilled_content

    def _parse_visual_directives(self, content: str) -> list[VisualDirective]:
        """
        解析内容中的所有 :::visual 指令块

        格式示例:
        :::visual {"id": "s1-fig-xxx", "action": "GENERATE_SVG", "description": "..."}
        详细描述内容...
        :::
        """
        directives = []

        # 匹配 :::visual ... ::: 块
        pattern = r':::visual[^\n]*\n[\s\S]*?:::'

        for match in re.finditer(pattern, content):
            raw_block = match.group(0)
            lines = raw_block.splitlines()
            header_line = lines[0].strip()
            body_content = "\n".join(lines[1:-1]).strip()
            json_config = header_line[len(":::visual"):].strip()

            directive = VisualDirective(
                raw_block=raw_block,
                start_pos=match.start(),
                end_pos=match.end()
            )

            # 解析 JSON 配置
            try:
                config = json.loads(json_config) if json_config else {}
                directive.id = config.get("id", f"visual-{len(directives)}")

                # 解析 action
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
                # 使用 body 作为描述
                directive.description = body_content

            # 如果描述为空，使用 body
            if not directive.description:
                directive.description = body_content

            directives.append(directive)

        return directives

    def _fulfill_directive(
        self,
        directive: VisualDirective,
        uar,
        output_path: Path,
        namespace: str,
        workspace_path: Path
    ) -> VisualDirective:
        """
        履约单个指令
        """
        if directive.action == AssetFulfillmentAction.SKIP:
            directive.fulfilled = True
            directive.result_html = f"<!-- SKIPPED: {directive.id} -->"
            return directive

        if directive.action == AssetFulfillmentAction.USE_EXISTING:
            return self._fulfill_use_existing(directive, uar, namespace, workspace_path)

        if directive.action == AssetFulfillmentAction.GENERATE_SVG:
            return self._fulfill_generate_svg(directive, uar, output_path, namespace, workspace_path)

        if directive.action == AssetFulfillmentAction.GENERATE_MERMAID:
            return self._fulfill_generate_mermaid(directive, namespace)

        if directive.action == AssetFulfillmentAction.SEARCH_WEB:
            return self._fulfill_search_web(directive, uar, output_path, namespace)

        directive.error = f"未知的 action 类型: {directive.action}"
        return directive

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

    def _fulfill_use_existing(
        self,
        directive: VisualDirective,
        uar,
        namespace: str = "",
        workspace_path: Optional[Path] = None
    ) -> VisualDirective:
        """使用现有资产"""
        asset_id = directive.matched_asset_id
        if not asset_id or asset_id not in uar.assets:
            directive.error = f"未找到资产: {asset_id}"
            return directive

        asset = uar.assets[asset_id]

        # 更新使用统计
        section_id = namespace or "unknown"
        asset.increment_usage(section_id)

        # 如果有焦点描述，计算并应用焦点 (同步路径)
        if directive.focus and workspace_path and not self.skip_generation:
            self.apply_focus_to_asset(asset, directive.focus, workspace_path, uar)

        directive.fulfilled = True
        directive.result_asset_id = asset_id
        directive.result_html = self._generate_figure_html(asset, directive.description)

        return directive

    async def _fulfill_use_existing_async(
        self,
        directive: VisualDirective,
        uar,
        namespace: str = "",
        workspace_path: Optional[Path] = None
    ) -> VisualDirective:
        """异步使用现有资产（支持焦点计算）"""
        asset_id = directive.matched_asset_id
        if not asset_id or asset_id not in uar.assets:
            directive.error = f"未找到资产: {asset_id}"
            return directive

        asset = uar.assets[asset_id]

        # 更新使用统计
        section_id = namespace or "unknown"
        asset.increment_usage(section_id)

        # 如果有焦点描述，计算并应用焦点 (MTODO 智能焦点计算)
        if directive.focus and workspace_path and not self.skip_generation:
            await self.apply_focus_to_asset_async(asset, directive.focus, workspace_path, uar)

        directive.fulfilled = True
        directive.result_asset_id = asset_id
        directive.result_html = self._generate_figure_html(asset, directive.description)

        return directive

    def _fulfill_generate_svg(
        self,
        directive: VisualDirective,
        uar,
        output_path: Path,
        namespace: str,
        workspace_path: Path
    ) -> VisualDirective:
        """生成 SVG 图形"""
        if self.skip_generation:
            # 测试模式：生成占位符
            directive.fulfilled = True
            directive.result_html = f'''<figure>
<div class="svg-placeholder" data-directive-id="{directive.id}">
  [SVG 占位符: {directive.description[:50]}...]
</div>
<figcaption>{directive.description}</figcaption>
</figure>'''
            return directive

        # 构建提示词
        style_hints = ""
        if directive.style_hints:
            style_hints = f"## 额外风格要求\n{directive.style_hints}"

        prompt = SVG_GENERATION_PROMPT.format(
            description=directive.description,
            style_hints=style_hints
        )

        try:
            # 调用 LLM 生成 SVG
            response = self.client.generate(
                prompt,
                system_instruction="你是一个专业的 SVG 矢量图形设计师。请生成清晰、教育性强的 SVG 图形。"
            )

            # 提取 SVG 代码
            svg_code = self._extract_svg(response.text)
            if not svg_code:
                directive.error = "未能从响应中提取 SVG 代码"
                return directive

            # 保存 SVG 文件
            filename = f"{directive.id}.svg"
            svg_path = output_path / filename
            svg_path.write_text(svg_code, encoding="utf-8")

            # 计算哈希
            content_hash = hashlib.md5(svg_code.encode()).hexdigest()

            # 创建资产条目
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
                quality_level=AssetQualityLevel.HIGH,  # AI 生成的 SVG 默认高质量
                quality_notes="AI 生成的矢量图形",
                suitable_for=["教学演示", "概念说明"],
            )
            asset_entry.increment_usage(namespace or "unknown")

            # 注册到 UAR
            uar.register_immediate(asset_entry)

            directive.fulfilled = True
            directive.result_asset_id = directive.id
            directive.result_html = self._generate_figure_html(asset_entry, directive.description)

        except Exception as e:
            directive.error = f"SVG 生成失败: {e}"

        return directive

    def _fulfill_generate_mermaid(self, directive: VisualDirective, namespace: str) -> VisualDirective:
        """生成 Mermaid 图表"""
        if self.skip_generation:
            directive.fulfilled = True
            directive.result_html = f'''<div class="mermaid-placeholder" data-directive-id="{directive.id}">
```mermaid
graph TD
    A[占位符] --> B[{directive.description[:30]}...]
```
</div>'''
            return directive

        # 构建提示词
        style_hints = ""
        if directive.style_hints:
            style_hints = f"## 额外要求\n{directive.style_hints}"

        prompt = MERMAID_GENERATION_PROMPT.format(
            description=directive.description,
            style_hints=style_hints
        )

        try:
            response = self.client.generate(
                prompt,
                system_instruction="你是一个 Mermaid 图表专家。请生成结构清晰的图表代码。"
            )

            # 提取 Mermaid 代码
            mermaid_code = self._extract_mermaid(response.text)
            if not mermaid_code:
                directive.error = "未能从响应中提取 Mermaid 代码"
                return directive

            directive.fulfilled = True
            directive.result_html = f'''<figure>
<div class="mermaid">
{mermaid_code}
</div>
<figcaption>{directive.description}</figcaption>
</figure>'''

        except Exception as e:
            directive.error = f"Mermaid 生成失败: {e}"

        return directive

    def _fulfill_search_web(
        self,
        directive: VisualDirective,
        uar,
        output_path: Path,
        namespace: str
    ) -> VisualDirective:
        """搜索网络图片"""
        if self.skip_search:
            directive.fulfilled = True
            directive.result_html = f'''<figure>
<div class="web-image-placeholder" data-directive-id="{directive.id}">
  [网络图片占位符: {directive.description[:50]}...]
</div>
<figcaption>{directive.description}</figcaption>
</figure>'''
            return directive

        # TODO: 实现实际的网络搜索逻辑
        # 这里需要集成图片搜索 API (如 Google Custom Search, Bing Image Search 等)
        directive.error = "网络搜索功能尚未实现"
        return directive

    # ============================================================================
    # 异步生成方法
    # ============================================================================

    async def _fulfill_generate_svg_async(
        self,
        directive: VisualDirective,
        uar,
        output_path: Path,
        namespace: str,
        workspace_path: Path
    ) -> VisualDirective:
        """异步生成 SVG 图形"""
        if self.skip_generation:
            directive.fulfilled = True
            directive.result_html = f'''<figure>
<div class="svg-placeholder" data-directive-id="{directive.id}">
  [SVG 占位符: {directive.description[:50]}...]
</div>
<figcaption>{directive.description}</figcaption>
</figure>'''
            return directive

        # 构建提示词
        style_hints = ""
        if directive.style_hints:
            style_hints = f"## 额外风格要求\n{directive.style_hints}"

        prompt = SVG_GENERATION_PROMPT.format(
            description=directive.description,
            style_hints=style_hints
        )

        try:
            # 异步调用 LLM 生成 SVG
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一个专业的 SVG 矢量图形设计师。请生成清晰、教育性强的 SVG 图形。",
                temperature=0.5
            )

            if not response.success:
                directive.error = f"SVG 生成 API 错误: {response.error}"
                return directive

            # 提取 SVG 代码
            svg_code = self._extract_svg(response.text)
            if not svg_code:
                directive.error = "未能从响应中提取 SVG 代码"
                return directive

            # 保存 SVG 文件
            filename = f"{directive.id}.svg"
            svg_path = output_path / filename
            svg_path.write_text(svg_code, encoding="utf-8")

            # 计算哈希
            content_hash = hashlib.md5(svg_code.encode()).hexdigest()

            # 创建资产条目
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
                quality_level=AssetQualityLevel.HIGH,
                quality_notes="AI 生成的矢量图形",
                suitable_for=["教学演示", "概念说明"],
            )
            asset_entry.increment_usage(namespace or "unknown")

            # 注册到 UAR
            uar.register_immediate(asset_entry)

            directive.fulfilled = True
            directive.result_asset_id = directive.id
            directive.result_html = self._generate_figure_html(asset_entry, directive.description)

            print(f"    - SVG 已保存: {svg_path.name}")

        except Exception as e:
            directive.error = f"SVG 生成失败: {e}"

        return directive

    async def _fulfill_generate_mermaid_async(self, directive: VisualDirective, namespace: str) -> VisualDirective:
        """异步生成 Mermaid 图表"""
        if self.skip_generation:
            directive.fulfilled = True
            directive.result_html = f'''<div class="mermaid-placeholder" data-directive-id="{directive.id}">
```mermaid
graph TD
    A[占位符] --> B[{directive.description[:30]}...]
```
</div>'''
            return directive

        # 构建提示词
        style_hints = ""
        if directive.style_hints:
            style_hints = f"## 额外要求\n{directive.style_hints}"

        prompt = MERMAID_GENERATION_PROMPT.format(
            description=directive.description,
            style_hints=style_hints
        )

        try:
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一个 Mermaid 图表专家。请生成结构清晰的图表代码。",
                temperature=0.5
            )

            if not response.success:
                directive.error = f"Mermaid 生成 API 错误: {response.error}"
                return directive

            # 提取 Mermaid 代码
            mermaid_code = self._extract_mermaid(response.text)
            if not mermaid_code:
                directive.error = "未能从响应中提取 Mermaid 代码"
                return directive

            directive.fulfilled = True
            directive.result_html = f'''<figure>
<div class="mermaid">
{mermaid_code}
</div>
<figcaption>{directive.description}</figcaption>
</figure>'''

            print(f"    - Mermaid 已生成: {directive.id}")

        except Exception as e:
            directive.error = f"Mermaid 生成失败: {e}"

        return directive

    def _extract_svg(self, text: str) -> Optional[str]:
        """从文本中提取 SVG 代码"""
        # 尝试匹配 ```svg ... ``` 块
        match = re.search(r'```svg\s*([\s\S]*?)```', text)
        if match:
            return match.group(1).strip()

        # 尝试直接匹配 <svg ...> ... </svg>
        match = re.search(r'<svg[^>]*>[\s\S]*?</svg>', text, re.IGNORECASE)
        if match:
            return match.group(0)

        return None

    def _extract_mermaid(self, text: str) -> Optional[str]:
        """从文本中提取 Mermaid 代码"""
        match = re.search(r'```mermaid\s*([\s\S]*?)```', text)
        if match:
            return match.group(1).strip()
        return None

    def _generate_figure_html(self, asset: AssetEntry, caption: str) -> str:
        """生成图片的 HTML figure 标签"""
        # SVG 技术图表使用 contain 避免裁剪标注文字
        if asset.local_path and asset.local_path.lower().endswith('.svg'):
            if asset.crop_metadata.object_fit == "cover":
                asset.crop_metadata.object_fit = "contain"
        img_tag = asset.to_img_tag()
        return f'''<figure>
{img_tag}
<figcaption>{caption}</figcaption>
</figure>'''

    def compute_focus_for_image(
        self,
        image_path: Path,
        focus_description: str
    ) -> Optional[CropMetadata]:
        """
        使用 VLM 计算图片的焦点位置

        Args:
            image_path: 图片文件路径
            focus_description: 焦点描述

        Returns:
            CropMetadata 或 None
        """
        import base64

        if not image_path.exists():
            return None

        # 读取图片
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # 确定 MIME 类型
        ext = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")

        # 构建多模态请求
        prompt = FOCUS_CALCULATION_PROMPT.format(focus_description=focus_description)
        parts = [
            {"text": prompt},
            {"inlineData": {"mimeType": mime_type, "data": image_data}},
        ]

        try:
            response = self.client.generate(
                parts=parts,
                system_instruction="你是一个视觉分析专家。请精确定位图片中的焦点区域。"
            )

            # 解析 JSON 响应
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return CropMetadata(
                    left=data.get("left", "50%"),
                    top=data.get("top", "50%"),
                    zoom=float(data.get("zoom", 1.0)),
                )
        except Exception as e:
            print(f"[AssetFulfillment] 焦点计算失败: {e}")

        return None

    async def compute_focus_for_image_async(
        self,
        image_path: Path,
        focus_description: str
    ) -> Optional[CropMetadata]:
        """
        异步使用 VLM 计算图片的焦点位置

        Args:
            image_path: 图片文件路径
            focus_description: 焦点描述

        Returns:
            CropMetadata 或 None
        """
        import base64

        if not image_path.exists():
            return None

        # 读取图片
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # 确定 MIME 类型
        ext = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")

        # 构建多模态请求
        prompt = FOCUS_CALCULATION_PROMPT.format(focus_description=focus_description)
        parts = [
            {"text": prompt},
            {"inlineData": {"mimeType": mime_type, "data": image_data}},
        ]

        try:
            response = await self.client.generate_async(
                parts=parts,
                system_instruction="你是一个视觉分析专家。请精确定位图片中的焦点区域。"
            )

            # 解析 JSON 响应
            json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return CropMetadata(
                    left=data.get("left", "50%"),
                    top=data.get("top", "50%"),
                    zoom=float(data.get("zoom", 1.0)),
                )
        except Exception as e:
            print(f"[AssetFulfillment] 焦点计算失败: {e}")

        return None

    def apply_focus_to_asset(
        self,
        asset: AssetEntry,
        focus_description: str,
        workspace_path: Path,
        uar=None
    ) -> None:
        """
        同步为资产计算并应用焦点 (智能焦点计算)
        """
        if not focus_description or not asset.local_path:
            return

        asset_path = Path(asset.local_path)
        if not asset_path.is_absolute():
            asset_path = workspace_path / asset.local_path

        if asset_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            crop_meta = self.compute_focus_for_image(asset_path, focus_description)
            if crop_meta:
                asset.crop_metadata = crop_meta
                if uar:
                    uar.register_immediate(asset)
                print(f"    [Focus] 已应用焦点: {crop_meta.left} {crop_meta.top} (zoom {crop_meta.zoom})")

    async def apply_focus_to_asset_async(
        self,
        asset: AssetEntry,
        focus_description: str,
        workspace_path: Path,
        uar=None
    ) -> None:
        """
        为资产计算并应用焦点 (智能焦点计算)

        Args:
            asset: 资产条目
            focus_description: 焦点描述
            workspace_path: 工作目录
        """
        if not focus_description or not asset.local_path:
            return

        # 构建完整路径
        asset_path = Path(asset.local_path)
        if not asset_path.is_absolute():
            asset_path = workspace_path / asset.local_path

        # 只对图片资产计算焦点（SVG 不需要）
        if asset_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            crop_meta = await self.compute_focus_for_image_async(asset_path, focus_description)
            if crop_meta:
                asset.crop_metadata = crop_meta
                if uar:
                    uar.register_immediate(asset)
                print(f"    [Focus] 已应用焦点: {crop_meta.left} {crop_meta.top} (zoom {crop_meta.zoom})")


# ============================================================================
# 便捷函数
# ============================================================================

def fulfill_section_assets(
    state: AgentState,
    section_content: str,
    namespace: str,
    skip_generation: bool = False,
    skip_search: bool = False
) -> tuple[AgentState, str]:
    """
    履约章节资产的便捷函数

    Example:
        state, fulfilled_content = fulfill_section_assets(
            state, writer_output, "s1"
        )
    """
    agent = AssetFulfillmentAgent(
        skip_generation=skip_generation,
        skip_search=skip_search
    )
    return agent.run(state, section_content, namespace)
