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
import base64
from pathlib import Path
from typing import Optional
from ..core.gemini_client import GeminiClient
from ..core.types import (
    AgentState,
    AssetEntry,
    AssetSource,
    AssetVQAStatus,
    AssetQualityLevel,
    ReusePolicy,
    CropMetadata,
    UniversalAssetRegistry,
)


# 支持的图片格式
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}

# Vision API 提示词 (SOTA 2.0: 包含质量评估)
VISION_TAGGING_PROMPT = """你是一个专业的图片内容分析师和质量评估师。请分析这张图片并提供以下信息：

## 必填信息

1. **semantic_label**: 用一句简洁的中文描述图片的核心内容，便于后续语义匹配。
   - 格式: 名词短语 + 内容描述
   - 示例: "心电图 P 波形成示意图", "人体心脏解剖结构图"

2. **tags**: 提供 3-5 个关键词标签 (英文小写)。
   - 示例: ["ecg", "heart", "p-wave", "cardiac"]

3. **quality_level**: 评估图片质量等级
   - HIGH: 高质量 - 清晰、专业、无水印、适合教学/出版
   - MEDIUM: 中等质量 - 基本清晰、可用但有小瑕疵
   - LOW: 低质量 - 模糊、有明显水印、分辨率低、不建议使用

4. **quality_notes**: 质量评估说明 (如有问题请详细说明)
   - 示例: "图片清晰度高，标注专业" 或 "有水印，分辨率偏低"

## 可选信息

5. **suitable_for**: 适用场景列表
   - 示例: ["概念说明", "教学演示", "流程图示"]

6. **unsuitable_for**: 不适用场景列表
   - 示例: ["精确数据展示", "临床诊断参考", "学术论文配图"]

7. **suggested_focus**: 如果图片有明显的视觉焦点，描述其位置
   - 示例: "中心偏左的心脏轮廓"

请以 JSON 格式输出：
```json
{
  "semantic_label": "...",
  "tags": ["tag1", "tag2", "tag3"],
  "quality_level": "HIGH|MEDIUM|LOW",
  "quality_notes": "...",
  "suitable_for": ["场景1", "场景2"],
  "unsuitable_for": ["场景1"],
  "suggested_focus": "..."
}
```

**重要**: 请严格评估质量，宁可评低不要评高。低质量图片会影响最终产出的专业性。
"""


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
        if os.path.isabs(self.input_dir):
            scan_path = Path(self.input_dir)
        else:
            # 相对于工作目录的父目录 (项目根目录)
            workspace = Path(state.workspace_path)
            scan_path = workspace.parent.parent / self.input_dir

        if not scan_path.exists():
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

    def _scan_images(self, directory: Path) -> list[Path]:
        """扫描目录下的所有图片文件"""
        images = []
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            images.extend(directory.glob(f"*{ext}"))
            images.extend(directory.glob(f"*{ext.upper()}"))
        return sorted(images)

    def _process_image(
        self,
        image_path: Path,
        base_dir: Path,
        uar: UniversalAssetRegistry
    ) -> Optional[AssetEntry]:
        """
        处理单个图片文件

        Args:
            image_path: 图片文件路径
            base_dir: 基准目录 (用于计算相对路径)
            uar: 资产注册表

        Returns:
            AssetEntry 或 None
        """
        # 计算内容哈希
        content_hash = self._compute_hash(image_path)

        # 检查是否已存在 (去重)
        for existing in uar.assets.values():
            if existing.content_hash == content_hash:
                print(f"  - 跳过重复: {image_path.name}")
                return None

        # 生成语义标签和质量评估
        if self.skip_vision:
            vision_result = {
                "semantic_label": f"图片: {image_path.stem}",
                "tags": [image_path.stem.lower()],
                "quality_level": AssetQualityLevel.UNASSESSED,
                "quality_notes": None,
                "suitable_for": [],
                "unsuitable_for": [],
                "suggested_focus": None,
            }
        else:
            vision_result = self._analyze_image(image_path)

        # 生成资产 ID
        asset_id = uar.generate_id("u", image_path.stem)  # u = user input namespace

        # 计算相对路径
        try:
            relative_path = image_path.relative_to(base_dir.parent)
        except ValueError:
            relative_path = image_path

        # 构建裁切元数据
        crop_metadata = CropMetadata()
        suggested_focus = vision_result.get("suggested_focus")
        if suggested_focus:
            # 简单解析焦点建议 (可以后续用 VLM 精确计算)
            if "左" in suggested_focus:
                crop_metadata.left = "30%"
            elif "右" in suggested_focus:
                crop_metadata.left = "70%"
            if "上" in suggested_focus:
                crop_metadata.top = "30%"
            elif "下" in suggested_focus:
                crop_metadata.top = "70%"

        # 创建资产条目 (SOTA 2.0: 包含质量评估)
        entry = AssetEntry(
            id=asset_id,
            source=AssetSource.USER,
            local_path=str(relative_path),
            semantic_label=vision_result["semantic_label"],
            content_hash=content_hash,
            crop_metadata=crop_metadata,
            alt_text=vision_result["semantic_label"],
            tags=vision_result["tags"],
            vqa_status=AssetVQAStatus.SKIPPED,  # 用户素材默认跳过 VQA
            reuse_policy=ReusePolicy.ALWAYS,
            # SOTA 2.0: 质量评估字段
            quality_level=vision_result["quality_level"],
            quality_notes=vision_result.get("quality_notes"),
            suitable_for=vision_result.get("suitable_for", []),
            unsuitable_for=vision_result.get("unsuitable_for", []),
        )

        return entry

    def _compute_hash(self, file_path: Path) -> str:
        """计算文件内容的 MD5 哈希"""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _analyze_image(self, image_path: Path) -> dict:
        """
        使用 Vision API 分析图片 (SOTA 2.0: 包含质量评估)

        Returns:
            包含以下字段的字典:
            - semantic_label: 语义描述
            - tags: 标签列表
            - quality_level: 质量等级 (AssetQualityLevel)
            - quality_notes: 质量备注
            - suitable_for: 适用场景
            - unsuitable_for: 不适用场景
            - suggested_focus: 建议焦点
        """
        # 默认返回值
        default_result = {
            "semantic_label": f"图片: {image_path.stem}",
            "tags": [image_path.stem.lower()],
            "quality_level": AssetQualityLevel.UNASSESSED,
            "quality_notes": None,
            "suitable_for": [],
            "unsuitable_for": [],
            "suggested_focus": None,
        }

        # 读取图片并编码为 base64
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
            ".svg": "image/svg+xml",
            ".bmp": "image/bmp",
        }
        mime_type = mime_types.get(ext, "image/png")

        # 构建多模态请求
        parts = [
            {"text": VISION_TAGGING_PROMPT},
            {"inlineData": {"mimeType": mime_type, "data": image_data}},
        ]

        # 调用 Vision API
        try:
            response = self.client.generate(
                parts=parts,
                system_instruction="你是一个专业的图片内容分析师和质量评估师。请严格按照要求输出 JSON 格式。"
            )

            # 解析 JSON 响应
            import json
            import re

            text = response.text

            # 提取 JSON (支持嵌套对象)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                # 解析质量等级
                quality_str = data.get("quality_level", "UNASSESSED").upper()
                quality_level = {
                    "HIGH": AssetQualityLevel.HIGH,
                    "MEDIUM": AssetQualityLevel.MEDIUM,
                    "LOW": AssetQualityLevel.LOW,
                }.get(quality_str, AssetQualityLevel.UNASSESSED)

                return {
                    "semantic_label": data.get("semantic_label", default_result["semantic_label"]),
                    "tags": data.get("tags", default_result["tags"]),
                    "quality_level": quality_level,
                    "quality_notes": data.get("quality_notes"),
                    "suitable_for": data.get("suitable_for", []),
                    "unsuitable_for": data.get("unsuitable_for", []),
                    "suggested_focus": data.get("suggested_focus"),
                }

        except Exception as e:
            print(f"    [Vision API 错误] {e}")

        return default_result

    async def run_async(self, state: AgentState) -> AgentState:
        """
        异步执行资产索引 (避免 asyncio.run() 嵌套问题)

        Args:
            state: Agent 状态

        Returns:
            更新后的状态 (包含初始化的 UAR)
        """
        print(f"[AssetIndexer] 开始扫描输入目录: {self.input_dir}")

        # 初始化 UAR
        uar = state.initialize_uar()

        # 确定扫描路径
        if os.path.isabs(self.input_dir):
            scan_path = Path(self.input_dir)
        else:
            workspace = Path(state.workspace_path)
            scan_path = workspace.parent.parent / self.input_dir

        if not scan_path.exists():
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

    async def _process_image_async(
        self,
        image_path: Path,
        base_dir: Path,
        uar: UniversalAssetRegistry
    ) -> Optional[AssetEntry]:
        """异步处理单个图片文件"""
        # 计算内容哈希
        content_hash = self._compute_hash(image_path)

        # 检查是否已存在 (去重)
        for existing in uar.assets.values():
            if existing.content_hash == content_hash:
                print(f"  - 跳过重复: {image_path.name}")
                return None

        # 生成语义标签和质量评估
        if self.skip_vision:
            vision_result = {
                "semantic_label": f"图片: {image_path.stem}",
                "tags": [image_path.stem.lower()],
                "quality_level": AssetQualityLevel.UNASSESSED,
                "quality_notes": None,
                "suitable_for": [],
                "unsuitable_for": [],
                "suggested_focus": None,
            }
        else:
            vision_result = await self._analyze_image_async(image_path)

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
        entry = AssetEntry(
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

        return entry

    async def _analyze_image_async(self, image_path: Path) -> dict:
        """
        异步使用 Vision API 分析图片 (避免 asyncio.run() 嵌套)
        """
        default_result = {
            "semantic_label": f"图片: {image_path.stem}",
            "tags": [image_path.stem.lower()],
            "quality_level": AssetQualityLevel.UNASSESSED,
            "quality_notes": None,
            "suitable_for": [],
            "unsuitable_for": [],
            "suggested_focus": None,
        }

        # 读取图片并编码为 base64
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
            ".svg": "image/svg+xml",
            ".bmp": "image/bmp",
        }
        mime_type = mime_types.get(ext, "image/png")

        # 构建多模态请求
        parts = [
            {"text": VISION_TAGGING_PROMPT},
            {"inlineData": {"mimeType": mime_type, "data": image_data}},
        ]

        # 调用 Vision API (异步)
        try:
            response = await self.client.generate_async(
                parts=parts,
                system_instruction="你是一个专业的图片内容分析师和质量评估师。请严格按照要求输出 JSON 格式。"
            )

            # 解析 JSON 响应
            import json
            import re

            text = response.text

            # 提取 JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                # 解析质量等级
                quality_str = data.get("quality_level", "UNASSESSED").upper()
                quality_level = {
                    "HIGH": AssetQualityLevel.HIGH,
                    "MEDIUM": AssetQualityLevel.MEDIUM,
                    "LOW": AssetQualityLevel.LOW,
                }.get(quality_str, AssetQualityLevel.UNASSESSED)

                return {
                    "semantic_label": data.get("semantic_label", default_result["semantic_label"]),
                    "tags": data.get("tags", default_result["tags"]),
                    "quality_level": quality_level,
                    "quality_notes": data.get("quality_notes"),
                    "suitable_for": data.get("suitable_for", []),
                    "unsuitable_for": data.get("unsuitable_for", []),
                    "suggested_focus": data.get("suggested_focus"),
                }

        except Exception as e:
            print(f"    [Vision API 错误] {e}")

        return default_result


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
