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
    AssetPriority,
    AssetVQAStatus,
    AssetQualityLevel,
    ReusePolicy,
    CropMetadata,
    UniversalAssetRegistry,
)
from .processors.vision import analyze_image, analyze_image_async
import base64


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
        异步执行资产索引与选择 (Modular Mounting Upgrade + Intent-Layered Support)
        """
        print(f"[AssetIndexer] 开始扫描输入目录: {self.input_dir}")

        # 1. 初始化 UAR 并扫描本地 inputs
        uar = state.initialize_uar()
        root_scan_path = self._resolve_scan_path(state)
        
        if root_scan_path and root_scan_path.exists():
            # 扫描策略：
            # 1. inputs/mandatory/ -> Priority.MANDATORY
            # 2. inputs/suggested/ -> Priority.SUGGESTED
            # 3. inputs/*.png (根目录) -> Priority.SUGGESTED (兼容旧版)
            
            subdirs = {
                "mandatory": AssetPriority.MANDATORY,
                "suggested": AssetPriority.SUGGESTED,
                ".": AssetPriority.SUGGESTED # 根目录图片
            }
            
            total_indexed = 0
            for dirname, priority in subdirs.items():
                scan_path = root_scan_path / dirname
                if not scan_path.exists():
                    continue
                
                # 只扫描当前文件夹，不递归（子文件夹逻辑由 subdirs 映射处理）
                image_files = []
                for ext in SUPPORTED_IMAGE_EXTENSIONS:
                    image_files.extend(scan_path.glob(f"*{ext}"))
                    image_files.extend(scan_path.glob(f"*{ext.upper()}"))
                
                print(f"[AssetIndexer] 扫描目录 {dirname}: 发现 {len(image_files)} 个图片")
                
                for img_path in sorted(image_files):
                    try:
                        entry = await self._process_image_async(img_path, root_scan_path, uar, priority=priority)
                        if entry:
                            uar.register_immediate(entry)
                            uar.add_to_whitelist(entry.id)
                            uar.user_provided_ids.add(entry.id)
                            total_indexed += 1
                    except Exception as e:
                        print(f"  ✗ 处理失败 {img_path.name}: {e}")
                        state.errors.append(f"AssetIndexer: {img_path.name} - {e}")
            
            print(f"[AssetIndexer] 成功注册 {total_indexed} 个本地输入资产")

        # 2. 处理挂载的工作区
        if uar.mounted_workspaces:
            await self._interactive_selection_flow(state, uar)

        return state

    async def _interactive_selection_flow(self, state: AgentState, uar: UniversalAssetRegistry):
        """交互式资产选择流"""
        print("\n" + "="*50)
        print("📦 模块化资产选择 (Modular Asset Selection)")
        print("="*50)

        # 列出所有挂载库中的资产
        all_external_assets = []
        for ws_name, assets in uar.mounted_workspaces.items():
            for asset in assets.values():
                all_external_assets.append((ws_name, asset))

        if not all_external_assets:
            print("  (挂载库中无可用资产)")
            return

        # A. 手动选择
        print(f"\n发现 {len(all_external_assets)} 个外部库资产。是否需要手动挑选？")
        choice = input("  输入 'y' 进入挑选，'n' 跳过，'all' 全部导入: ").strip().lower()

        if choice == 'all':
            for _, asset in all_external_assets:
                uar.add_to_whitelist(asset.id)
            print(f"  ✅ 已将所有 {len(all_external_assets)} 个资产加入白名单")
            return
        
        if choice == 'y':
            self._manual_selection_loop(all_external_assets, uar)

        # B. AI 智能推荐 (可选)
        print(f"\n是否需要 AI 根据您的需求 (“{state.user_intent[:50]}...”) 自动推荐资产？")
        ai_choice = input("  输入 'y' 运行智能扫描，'n' 跳过: ").strip().lower()

        if ai_choice == 'y':
            recommendations = await self._run_tier1_broad_search(state.user_intent, all_external_assets)
            if recommendations:
                print(f"\n🤖 AI 推荐了以下 {len(recommendations)} 个资产:")
                for i, aid in enumerate(recommendations, 1):
                    asset = uar.get_asset(aid)
                    label = asset.semantic_label if asset else "Unknown"
                    print(f"  {i}. [{aid}] {label}")
                
                confirm = input("\n  是否全部接受推荐并加入白名单？(y/n): ").strip().lower()
                if confirm == 'y':
                    for aid in recommendations:
                        uar.add_to_whitelist(aid)
                    print("  ✅ 推荐资产已入库")

    def _manual_selection_loop(self, assets_list: list, uar: UniversalAssetRegistry):
        """命令行手动挑选循环"""
        print("\n--- 资产列表 ---")
        for i, (ws, asset) in enumerate(assets_list, 1):
            status = " [已选]" if asset.id in uar.whitelisted_ids else ""
            print(f"  {i:2}. [{ws}] {asset.id}: {asset.semantic_label[:50]}...{status}")
        
        while True:
            print("\n请输入资产编号进行 勾选/取消 (例如 '1, 3, 5')，输入 'done' 完成:")
            cmd = input("  > ").strip().lower()
            if cmd == 'done':
                break
            
            try:
                indices = [int(x.strip()) for x in cmd.replace(',', ' ').split()]
                for idx in indices:
                    if 1 <= idx <= len(assets_list):
                        asset = assets_list[idx-1][1]
                        if asset.id in uar.whitelisted_ids:
                            uar.whitelisted_ids.remove(asset.id)
                            print(f"  - 已移除: {asset.id}")
                        else:
                            uar.add_to_whitelist(asset.id)
                            print(f"  + 已勾选: {asset.id}")
            except ValueError:
                print("  ❌ 输入无效，请使用数字编号")

    async def _run_tier1_broad_search(self, user_intent: str, assets_list: list) -> list[str]:
        """使用 Gemini Flash 进行第一层粗筛"""
        print("  [AI] 正在扫描库资产以匹配您的意图...")
        
        # 构造资产列表摘要
        catalog = []
        for _, asset in assets_list:
            catalog.append({
                "id": asset.id,
                "label": asset.semantic_label,
                "tags": asset.tags
            })

        prompt = f"""你是一位视觉资产检索专家。请根据用户的创作意图，从资产目录中筛选出最相关的 **Top 10** 个资产。

### 用户创作意图
{user_intent}

### 资产目录 (JSON)
{json.dumps(catalog[:100], ensure_ascii=False)} 

### 输出格式
请直接输出 JSON 格式的 ID 列表：
```json
{{
  "suggestions": ["id1", "id2", ...],
  "reason": "筛选理由"
}}
```
"""
        try:
            # 强制使用 Flash 模型进行粗筛
            response = await self.client.generate_async(
                prompt=prompt,
                system_instruction="你是一位专业的资产检索助手。请快速准确地筛选相关资产。",
                temperature=0.0
            )
            
            if response.success:
                import re
                match = re.search(r'\{[\s\S]*\}', response.text)
                if match:
                    data = json.loads(match.group())
                    return data.get("suggestions", [])
            return []
        except Exception as e:
            print(f"  [AssetIndexer] AI 粗筛失败: {e}")
            return []

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
        uar: UniversalAssetRegistry,
        priority: AssetPriority = AssetPriority.SUGGESTED
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

        return self._create_asset_entry(image_path, base_dir, uar, content_hash, vision_result, priority=priority)

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
        vision_result: dict,
        priority: AssetPriority = AssetPriority.SUGGESTED
    ) -> AssetEntry:
        """创建资产条目"""
        # 生成资产 ID
        asset_id = uar.generate_id("u", image_path.stem)

        # 计算相对路径 - 存储完整的项目根目录相对路径
        try:
            parts = image_path.parts
            if "assets" in parts:
                assets_idx = parts.index("assets")
                relative_path = Path(*parts[assets_idx:])
            else:
                relative_path = image_path.relative_to(base_dir.parent)
        except ValueError:
            relative_path = image_path

        # 缓存图像 Base64 数据 (用于多模态注入)
        base64_data = None
        try:
            with open(image_path, "rb") as f:
                base64_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"  [AssetIndexer] 无法读取图片数据进行缓存: {e}")

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
            priority=priority,
            local_path=str(relative_path),
            base64_data=base64_data,
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
