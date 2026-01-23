"""
Asset Management Models

Shared data structures for asset processing.
"""

from dataclasses import dataclass, field
from typing import Optional

from ...core.types import AssetFulfillmentAction


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
    reuse_score: int = 0  # 资产复用得分 (0-100)

    # 上下文感知 (Sliding Context)
    context_before: str = ""  # 指令块前的上下文文本
    context_after: str = ""   # 指令块后的上下文文本

    # 履约结果
    fulfilled: bool = False
    result_asset_id: Optional[str] = None
    result_html: Optional[str] = None
    error: Optional[str] = None

    def get_full_context(self) -> str:
        """获取包含上下文的完整描述，用于传递给 AI"""
        parts = []
        if self.context_before:
            parts.append(f"[CONTEXT BEFORE]\n{self.context_before}")
        parts.append(f"[DIRECTIVE]\n{self.description}")
        if self.context_after:
            parts.append(f"[CONTEXT AFTER]\n{self.context_after}")
        return "\n\n".join(parts)
