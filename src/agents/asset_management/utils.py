"""
Asset Management Utilities

Shared helper functions for asset processing.
"""

from pathlib import Path
from typing import Optional

from ...core.types import AssetEntry


import shutil
import asyncio

class WorkingCopyManager:
    """
    Manages a transactional .working copy of a file for incremental updates.
    Ensures thread-safe writes and atomic commits.
    """
    def __init__(self, original_path: Path):
        self.original_path = original_path
        self.working_path = original_path.with_suffix(original_path.suffix + ".working")
        self._lock = asyncio.Lock()

    def start_session(self) -> Path:
        """
        Ensures a .working file exists. If it already exists, we resume from it.
        Otherwise, we create it from the original.
        """
        if not self.working_path.exists():
            shutil.copy2(self.original_path, self.working_path)
            print(f"  [Fulfillment] Created working copy: {self.working_path.name}")
        else:
            print(f"  [Fulfillment] Resuming from existing working copy: {self.working_path.name}")
        return self.working_path

    async def update_content(self, new_content: str):
        """Thread-safe write to the working file."""
        async with self._lock:
            # We use to_thread for blocking IO
            await asyncio.to_thread(self.working_path.write_text, new_content, encoding="utf-8")

    def commit(self):
        """Atomic commit: rename .working back to original."""
        if self.working_path.exists():
            self.working_path.replace(self.original_path)
            print(f"  [Fulfillment] Committed changes to: {self.original_path.name}")

    def cleanup(self):
        """Remove .working file if it exists."""
        if self.working_path.exists():
            self.working_path.unlink()


def generate_figure_html(
    asset: AssetEntry,
    caption: str,
    md_subdir: str = "md",
    target_file: Optional[Path] = None,
    workspace_path: Optional[Path] = None
) -> str:
    """
    生成图片的 HTML figure 标签

    Args:
        asset: 资产条目
        caption: 图片说明
        md_subdir: markdown 文件所在的子目录名称 (用于计算相对路径)
        target_file: 正在写入的目标文件路径
        workspace_path: 当前工作目录

    Returns:
        HTML figure 代码
    """
    # SVG 技术图表使用 contain 避免裁剪标注文字
    if asset.local_path and asset.local_path.lower().endswith('.svg'):
        if asset.crop_metadata.object_fit == "cover":
            asset.crop_metadata.object_fit = "contain"

    # 计算从 md_subdir 到资产的正确相对路径
    img_tag = asset.to_img_tag(
        target_file=target_file, 
        workspace_path=workspace_path, 
        md_subdir=md_subdir
    )
    # SOTA Rendering: Ensure blank lines are NAKED (no indents) to trigger Markdown parsers
    return f'<figure>\n{img_tag}\n<figcaption>\n\n{caption}\n\n</figcaption>\n</figure>'


def generate_placeholder_html(directive_id: str, description: str, placeholder_type: str = "svg") -> str:
    """
    生成占位符 HTML（用于测试模式）

    Args:
        directive_id: 指令 ID
        description: 描述文本
        placeholder_type: 占位符类型 (svg, mermaid, web-image)

    Returns:
        占位符 HTML 代码
    """
    short_desc = description[:50] + "..." if len(description) > 50 else description
    return f'''<figure>
<div class="{placeholder_type}-placeholder" data-directive-id="{directive_id}">
  [{placeholder_type.upper()} 占位符: {short_desc}]
</div>
<figcaption>{description}</figcaption>
</figure>'''


def generate_mermaid_html(mermaid_code: str, caption: str) -> str:
    """
    生成 Mermaid 图表的 HTML

    Args:
        mermaid_code: Mermaid 代码
        caption: 图表说明

    Returns:
        HTML figure 代码
    """
    return f'''<figure>
<div class="mermaid">
{mermaid_code}
</div>
<figcaption>{caption}</figcaption>
</figure>'''


def resolve_asset_path(
    asset: AssetEntry,
    workspace_path: Path
) -> Optional[Path]:
    """
    解析资产的完整路径

    Args:
        asset: 资产条目
        workspace_path: 工作目录路径

    Returns:
        完整路径或 None
    """
    if not asset.local_path:
        return None

    local_path = Path(asset.local_path)

    # 如果已经是绝对路径
    if local_path.is_absolute():
        return local_path if local_path.exists() else None

    # 尝试相对于 workspace
    full_path = workspace_path / local_path
    if full_path.exists():
        return full_path

    # 尝试相对于 workspace 的父目录
    full_path = workspace_path.parent / local_path
    if full_path.exists():
        return full_path

    # 尝试相对于项目根目录
    full_path = workspace_path.parent.parent / local_path
    if full_path.exists():
        return full_path

    return None
