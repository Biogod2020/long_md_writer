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
import asyncio
import json
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
    资产索引器 Agent (SOTA 性能优化版)

    1. 支持 5 路并行 VLM 分析
    2. 基于文件哈希的全局增量索引 (跳过已扫描文件)
    """

    def __init__(
        self,
        client: Optional[GeminiClient] = None,
        input_dir: str = "inputs",
        skip_vision: bool = False,
        cache_dir: str = "data/asset_cache"
    ):
        self.client = client or GeminiClient()
        self.input_dir = input_dir
        self.skip_vision = skip_vision
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "vision_cache.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
            except:
                return {}
        return {}

    def _save_cache(self):
        self.cache_file.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8")

    async def run_async(self, state: AgentState) -> AgentState:
        print(f"[AssetIndexer] 开始扫描输入目录: {self.input_dir}")

        uar = state.initialize_uar()
        root_scan_path = self._resolve_scan_path(state)
        
        if not root_scan_path or not root_scan_path.exists():
            return state

        # 收集待扫描文件
        subdirs = ["mandatory", "suggested", "."]
        all_files_to_process = []
        for dirname in subdirs:
            scan_path = root_scan_path / dirname
            if not scan_path.exists(): continue
            for ext in SUPPORTED_IMAGE_EXTENSIONS:
                for img_path in scan_path.glob(f"*{ext}"):
                    all_files_to_process.append((img_path, dirname))
                for img_path in scan_path.glob(f"*{ext.upper()}"):
                    all_files_to_process.append((img_path, dirname))

        if not all_files_to_process:
            print("[AssetIndexer] 未发现新图片")
            return state

        # 5路并行控制
        semaphore = asyncio.Semaphore(5)
        print(f"[AssetIndexer] 准备分析 {len(all_files_to_process)} 个文件 (5路并行)...")

        async def indexed_task(img_path, dirname):
            async with semaphore:
                priority = AssetPriority.MANDATORY if dirname == "mandatory" else AssetPriority.SUGGESTED
                # 1. 计算哈希
                content_hash = self._compute_hash(img_path)
                
                # 2. 检查缓存
                if content_hash in self._cache:
                    print(f"  ⚡ 缓存命中 (Skip VLM): {img_path.name}")
                    vision_result = self._cache[content_hash]
                else:
                    # 3. 检查已挂载工作区
                    hit = None
                    for ws in uar.mounted_workspaces.values():
                        for a in ws.values():
                            if a.content_hash == content_hash:
                                hit = a
                                break
                        if hit: break
                    
                    if hit:
                        print(f"  ⚡ 库命中 (Skip VLM): {img_path.name} -> {hit.id}")
                        vision_result = {
                            "semantic_label": hit.semantic_label,
                            "tags": hit.tags,
                            "quality_level": hit.quality_level,
                            "suitable_for": hit.suitable_for,
                            "unsuitable_for": hit.unsuitable_for
                        }
                    else:
                        # 4. 真正调用 VLM
                        print(f"  🔍 正在分析新文件: {img_path.name}")
                        if self.skip_vision:
                            vision_result = self._get_default_vision_result(img_path)
                        else:
                            vision_result = await analyze_image_async(self.client, img_path)
                        
                        # 更新缓存
                        self._cache[content_hash] = vision_result

                # 5. 创建条目 (SOTA: 返回条目供后续批量注册)
                entry = self._create_asset_entry(img_path, root_scan_path, uar, content_hash, vision_result, priority=priority)
                return entry

        tasks = [indexed_task(path, d) for path, d in all_files_to_process]
        results = await asyncio.gather(*tasks)
        
        valid_entries = [r for r in results if r]
        if valid_entries:
            # SOTA: 统一原子化写入，杜绝竞争
            uar.register_batch(valid_entries)
            for entry in valid_entries:
                uar.add_to_whitelist(entry.id)
                uar.user_provided_ids.add(entry.id)
        
        print(f"[AssetIndexer] 扫描完成: 成功索引 {len(valid_entries)} 个资产")
        self._save_cache()

        if uar.mounted_workspaces:
            if getattr(state, "auto_mode", False):
                print("[AssetIndexer] AutoMode: 自动将所有挂载库资产加入白名单")
                for ws_name, assets in uar.mounted_workspaces.items():
                    for aid in assets.keys():
                        uar.add_to_whitelist(aid)
            else:
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
    import asyncio
    indexer = AssetIndexerAgent(input_dir=input_dir)
    return asyncio.run(indexer.run_async(state))


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
