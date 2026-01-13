"""
AssetIndexerAgent: SOTA 2.0 Phase 0 资产索引器

核心职责：
1. 扫描 inputs/ 目录下的所有图片文件
2. 调用 Vision API 生成语义描述 (semantic_label)
3. 计算内容指纹 (content_hash)
4. 初始化 UAR (Universal Asset Registry)

执行时机：
- 在 Clarifier 之前或并行执行
- 确保 UAR 在 Writer 开始创作前已就绪
"""

import os
import hashlib
from pathlib import Path
from typing import Optional

from ...core.gemini_client import GeminiClient
from ...core.types import (
    AgentState,
    AssetEntry,
    AssetSource,
    AssetVQAStatus,
    AssetQualityLevel,
    ReusePolicy,
    CropMetadata,
    UniversalAssetRegistry,
)
from .processors.vision import analyze_image, analyze_image_async


# 支持的图片格式
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}


class AssetIndexerAgent:
    """
    资产索引器 Agent

    扫描输入目录，为图片素材生成语义标签，初始化 UAR
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        input_dir: str = "inputs",
        skip_vision: bool = False
    ):
        """
        初始化资产索引器

        Args:
            client: Gemini API 客户端
            input_dir: 输入目录路径
            skip_vision: 跳过 Vision API 调用 (用于测试)
        """
        self.client = client or GeminiClient()
        self.input_dir = input_dir
        self.skip_vision = skip_vision

    def run(self, state: AgentState) -> AgentState:
        """
        执行资产索引

        Args:
            state: Agent 状态

        Returns:
            更新后的状态 (包含初始化的 UAR)
        """
        print(f"[AssetIndexer] 开始扫描输入目录: {self.input_dir}")

        # 初始化 UAR
        uar = state.initialize_uar()

        # 确定扫描路径
        scan_path = self._resolve_scan_path(state)
        if not scan_path or not scan_path.exists():
            print(f"[AssetIndexer] 警告: 输入目录不存在: {scan_path}")
            return state

        # 扫描图片文件
        image_files = self._scan_images(scan_path)
        print(f"[AssetIndexer] 发现 {len(image_files)} 个图片文件")

        # 处理每个图片
        entries = []
        for img_path in image_files:
            try:
                entry = self._process_image(img_path, scan_path, uar)
                if entry:
                    entries.append(entry)
                    print(f"  ✓ {entry.id}: {entry.semantic_label[:30]}...")
            except Exception as e:
                print(f"  ✗ 处理失败 {img_path.name}: {e}")
                state.errors.append(f"AssetIndexer: {img_path.name} - {e}")

        # 批量注册
        if entries:
            uar.register_batch(entries)
            print(f"[AssetIndexer] 成功注册 {len(entries)} 个资产")

        return state

    async def run_async(self, state: AgentState) -> AgentState:
        """
        异步执行资产索引

        Args:
            state: Agent 状态

        Returns:
            更新后的状态 (包含初始化的 UAR)
        """
        print(f"[AssetIndexer] 开始扫描输入目录: {self.input_dir}")

        # 初始化 UAR
        uar = state.initialize_uar()

        # 确定扫描路径
        scan_path = self._resolve_scan_path(state)
        if not scan_path or not scan_path.exists():
            print(f"[AssetIndexer] 警告: 输入目录不存在: {scan_path}")
            return state

        # 扫描图片文件
        image_files = self._scan_images(scan_path)
        print(f"[AssetIndexer] 发现 {len(image_files)} 个图片文件")

        # 处理每个图片 (异步)
        entries = []
        for img_path in image_files:
            try:
                entry = await self._process_image_async(img_path, scan_path, uar)
                if entry:
                    entries.append(entry)
                    print(f"  ✓ {entry.id}: {entry.semantic_label[:30]}...")
            except Exception as e:
                print(f"  ✗ 处理失败 {img_path.name}: {e}")
                state.errors.append(f"AssetIndexer: {img_path.name} - {e}")

        # 批量注册
        if entries:
            uar.register_batch(entries)
            print(f"[AssetIndexer] 成功注册 {len(entries)} 个资产")

        return state

    def _resolve_scan_path(self, state: AgentState) -> Optional[Path]:
        """解析扫描路径"""
        if os.path.isabs(self.input_dir):
            return Path(self.input_dir)
        else:
            workspace = Path(state.workspace_path)
            return workspace.parent.parent / self.input_dir

    def _scan_images(self, directory: Path) -> list[Path]:
        """扫描目录下的所有图片文件"""
        images = []
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            images.extend(directory.glob(f"*{ext}"))
            images.extend(directory.glob(f"*{ext.upper()}"))
        return sorted(images)

    def _compute_hash(self, file_path: Path) -> str:
        """计算文件内容的 MD5 哈希"""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _process_image(
        self,
        image_path: Path,
        base_dir: Path,
        uar: UniversalAssetRegistry
    ) -> Optional[AssetEntry]:
        """处理单个图片文件（同步）"""
        # 计算内容哈希
        content_hash = self._compute_hash(image_path)

        # 检查是否已存在 (去重)
        for existing in uar.assets.values():
            if existing.content_hash == content_hash:
                print(f"  - 跳过重复: {image_path.name}")
                return None

        # 生成语义标签和质量评估
        if self.skip_vision:
            vision_result = self._get_default_vision_result(image_path)
        else:
            vision_result = analyze_image(self.client, image_path)

        return self._create_asset_entry(image_path, base_dir, uar, content_hash, vision_result)

    async def _process_image_async(
        self,
        image_path: Path,
        base_dir: Path,
        uar: UniversalAssetRegistry
    ) -> Optional[AssetEntry]:
        """处理单个图片文件（异步）"""
        # 计算内容哈希
        content_hash = self._compute_hash(image_path)

        # 检查是否已存在 (去重)
        for existing in uar.assets.values():
            if existing.content_hash == content_hash:
                print(f"  - 跳过重复: {image_path.name}")
                return None

        # 生成语义标签和质量评估
        if self.skip_vision:
            vision_result = self._get_default_vision_result(image_path)
        else:
            vision_result = await analyze_image_async(self.client, image_path)

        return self._create_asset_entry(image_path, base_dir, uar, content_hash, vision_result)

    def _get_default_vision_result(self, image_path: Path) -> dict:
        """生成默认的视觉分析结果"""
        return {
            "semantic_label": f"图片: {image_path.stem}",
            "tags": [image_path.stem.lower()],
            "quality_level": AssetQualityLevel.UNASSESSED,
            "quality_notes": None,
            "suitable_for": [],
            "unsuitable_for": [],
            "suggested_focus": None,
        }

    def _create_asset_entry(
        self,
        image_path: Path,
        base_dir: Path,
        uar: UniversalAssetRegistry,
        content_hash: str,
        vision_result: dict
    ) -> AssetEntry:
        """创建资产条目"""
        # 生成资产 ID
        asset_id = uar.generate_id("u", image_path.stem)

        # 计算相对路径
        try:
            relative_path = image_path.relative_to(base_dir.parent)
        except ValueError:
            relative_path = image_path

        # 构建裁切元数据
        crop_metadata = CropMetadata()
        suggested_focus = vision_result.get("suggested_focus")
        if suggested_focus:
            if "左" in suggested_focus:
                crop_metadata.left = "30%"
            elif "右" in suggested_focus:
                crop_metadata.left = "70%"
            if "上" in suggested_focus:
                crop_metadata.top = "30%"
            elif "下" in suggested_focus:
                crop_metadata.top = "70%"

        # 创建资产条目
        return AssetEntry(
            id=asset_id,
            source=AssetSource.USER,
            local_path=str(relative_path),
            semantic_label=vision_result["semantic_label"],
            content_hash=content_hash,
            crop_metadata=crop_metadata,
            alt_text=vision_result["semantic_label"],
            tags=vision_result["tags"],
            vqa_status=AssetVQAStatus.SKIPPED,
            reuse_policy=ReusePolicy.ALWAYS,
            quality_level=vision_result["quality_level"],
            quality_notes=vision_result.get("quality_notes"),
            suitable_for=vision_result.get("suitable_for", []),
            unsuitable_for=vision_result.get("unsuitable_for", []),
        )


# ============================================================================
# 便捷函数
# ============================================================================

def index_user_assets(state: AgentState, input_dir: str = "inputs") -> AgentState:
    """
    索引用户资产的便捷函数

    Example:
        state = index_user_assets(state, "inputs")
        print(state.asset_registry.to_summary())
    """
    indexer = AssetIndexerAgent(input_dir=input_dir)
    return indexer.run(state)


async def index_user_assets_async(
    state: AgentState,
    client: GeminiClient,
    input_dir: str = "inputs"
) -> AgentState:
    """
    异步索引用户资产

    用于与其他 Agent 并行执行
    """
    indexer = AssetIndexerAgent(client=client, input_dir=input_dir)
    return await indexer.run_async(state)
