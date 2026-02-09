"""
Data types and models for the Magnum Opus HTML Agent system.

SOTA 2.0 升级：
- AssetEntry: 资产条目模型
- UniversalAssetRegistry (UAR): 统一资产注册表
- CropMetadata: 裁切元数据
"""

from typing import Optional, Literal, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
import json
from pathlib import Path
import hashlib
import os
from .path_utils import get_project_root


# ============================================================================
# SOTA 2.0: 资产管理系统 (Universal Asset Registry)
# ============================================================================

class AssetSource(str, Enum):
    """资产来源枚举"""
    USER = "USER"      # 用户本地输入 (inputs/ 目录)
    AI = "AI"          # AI 生成 (SVG, Mermaid 等)
    WEB = "WEB"        # 网络搜索获取


class AssetPriority(str, Enum):
    """资产优先级枚举 (SOTA 2.0)"""
    MANDATORY = "MANDATORY"    # 强制性资产 (必须出现在文中)
    SUGGESTED = "SUGGESTED"    # 建议性资产 (可选，评分高则用)
    AUTONOMOUS = "AUTONOMOUS"  # 发现性资产 (由 AI 完全自主决定)


class AssetVQAStatus(str, Enum):
    """资产视觉质检状态"""
    PENDING = "PENDING"    # 待审核
    PASS = "PASS"          # 通过
    FAIL = "FAIL"          # 不通过
    SKIPPED = "SKIPPED"    # 跳过审核


class ReusePolicy(str, Enum):
    """资产复用策略"""
    ALWAYS = "ALWAYS"   # 总是可复用
    ONCE = "ONCE"       # 仅使用一次
    NEVER = "NEVER"     # 不可复用 (如章节特定图)


class AssetQualityLevel(str, Enum):
    """资产质量等级"""
    HIGH = "HIGH"           # 高质量，可直接使用
    MEDIUM = "MEDIUM"       # 中等质量，可用但有局限
    LOW = "LOW"             # 低质量，不建议使用
    UNASSESSED = "UNASSESSED"  # 未评估


class AssetFulfillmentAction(str, Enum):
    """
    资产履约动作 - Writer 决策后的行动指令

    当 Writer 判断现有资产不适合时，指定应采取的行动
    """
    USE_EXISTING = "USE_EXISTING"     # 使用现有资产 (直接注入 <img>)
    GENERATE_SVG = "GENERATE_SVG"     # 拒绝现有资产，生成 SVG
    SEARCH_WEB = "SEARCH_WEB"         # 拒绝现有资产，启用网络搜图
    GENERATE_MERMAID = "GENERATE_MERMAID"  # 生成 Mermaid 图表
    SKIP = "SKIP"                     # 此处不需要图像


class CropMetadata(BaseModel):
    """裁切元数据 - 用于 CSS object-position 和 object-fit"""
    left: str = Field(default="50%", description="水平位置 (CSS object-position X)")
    top: str = Field(default="50%", description="垂直位置 (CSS object-position Y)")
    zoom: float = Field(default=1.0, description="缩放倍数")
    width: Optional[str] = Field(default=None, description="容器宽度 (如 '100%', '300px')")
    height: Optional[str] = Field(default=None, description="容器高度 (如 'auto', '200px')")
    object_fit: Literal["cover", "contain", "fill", "none", "scale-down"] = Field(
        default="cover", description="CSS object-fit 属性"
    )

    def to_inline_style(self) -> str:
        """生成内联 CSS 样式字符串"""
        styles = [f"object-position: {self.left} {self.top}"]
        styles.append(f"object-fit: {self.object_fit}")
        if self.width:
            styles.append(f"width: {self.width}")
        if self.height:
            styles.append(f"height: {self.height}")
        return "; ".join(styles)


class AssetEntry(BaseModel):
    """
    资产条目 - UAR 的基本单元

    设计理念：
    - 每个资产都有唯一的 namespace-qualified ID
    - semantic_label 用于 LLM 语义匹配
    - crop_metadata 存储裁切决策，供 Writer 直接注入 <img> 标签
    """
    id: str = Field(..., description="唯一标识符，带命名空间前缀 (如 's1-ecg-diagram')")
    source: AssetSource = Field(..., description="资产来源")
    priority: AssetPriority = Field(default=AssetPriority.SUGGESTED, description="资产优先级 (MANDATORY/SUGGESTED/AUTONOMOUS)")
    local_path: Optional[str] = Field(default=None, description="本地物理路径 (相对于 workspace)")
    base64_data: Optional[str] = Field(default=None, description="图像 Base64 数据缓存 (用于多模态注入)")
    original_url: Optional[str] = Field(default=None, description="原始 URL (仅 WEB 来源)")
    semantic_label: str = Field(..., description="语义描述，用于意图匹配 (如 '心电图 P 波形成示意图')")
    content_hash: Optional[str] = Field(default=None, description="内容指纹 (用于去重)")

    # 裁切与展示
    crop_metadata: CropMetadata = Field(default_factory=CropMetadata, description="裁切元数据")
    alt_text: Optional[str] = Field(default=None, description="替代文本 (无障碍)")
    caption: Optional[str] = Field(default=None, description="图片说明文字")

    # 版权与归属
    copyright_info: Optional[str] = Field(default=None, description="版权信息")
    attribution: Optional[str] = Field(default=None, description="署名归属")

    # 状态与策略
    vqa_status: AssetVQAStatus = Field(default=AssetVQAStatus.PENDING, description="VQA 状态")
    reuse_policy: ReusePolicy = Field(default=ReusePolicy.ALWAYS, description="复用策略")
    usage_count: int = Field(default=0, description="使用次数")

    # SOTA 2.0: 质量评估
    quality_level: AssetQualityLevel = Field(
        default=AssetQualityLevel.UNASSESSED,
        description="资产质量等级 (由 VLM 评估)"
    )
    quality_notes: Optional[str] = Field(
        default=None,
        description="质量评估备注 (如: '分辨率低', '水印明显', '内容不完整')"
    )
    suitable_for: list[str] = Field(
        default_factory=list,
        description="适用场景列表 (如: ['概念图示', '流程说明'])"
    )
    unsuitable_for: list[str] = Field(
        default_factory=list,
        description="不适用场景列表 (如: ['精确数据展示', '临床诊断参考'])"
    )

    # 关联信息
    used_in_sections: list[str] = Field(default_factory=list, description="使用该资产的章节 ID 列表")
    tags: list[str] = Field(default_factory=list, description="标签 (用于分类检索)")
    rejection_history: list[dict] = Field(
        default_factory=list,
        description="被拒绝使用的历史记录 [{section_id, reason, suggested_action}]"
    )

    def get_absolute_path(self, workspace_path: Optional[Union[str, Path]] = None, project_root: Optional[Path] = None) -> Optional[Path]:
        """
        Intelligently resolves the absolute physical path of the asset.
        Returns the most likely absolute path, even if it doesn't exist on disk.
        """
        if not self.local_path:
            return None

        local_path = Path(self.local_path)
        if local_path.is_absolute():
            return local_path

        # 1. Try relative to provided workspace_path
        ws_path = Path(workspace_path).resolve() if workspace_path else None
        if ws_path:
            # Try directly in workspace
            full = ws_path / local_path
            if full.exists():
                return full
            # Try in parent of workspace (common for jobs in workspaces/workspace/)
            full = ws_path.parent / local_path
            if full.exists():
                return full

        # 2. Try relative to project root
        root = project_root or get_project_root(start_path=ws_path)
        full = root / local_path
        if full.exists():
            return full

        # 3. Fallback: Return best guess relative to project root if nothing else found
        return (root / local_path).resolve()

    def to_img_tag(self, class_name: Optional[str] = None, target_file: Optional[Union[str, Path]] = None, workspace_path: Optional[Union[str, Path]] = None, md_subdir: Optional[str] = None, project_root: Optional[Path] = None) -> str:
        """
        生成完整的 <img> HTML 标签 (Writer-Direct-Inject 协议)

        示例输出:
        <img src="assets/images/s1-ecg-diagram.png"
             alt="心电图 P 波形成示意图"
             style="object-position: 30% 20%; object-fit: cover; width: 100%"
             class="figure-main">

        Args:
            class_name: 可选的 CSS 类名
            target_file: 正在生成的 Markdown/HTML 文件的路径 (用于计算相对路径)
            workspace_path: 当前任务的工作目录
            md_subdir: (已弃用) markdown 文件所在的子目录 (如 "md")
            project_root: 可选的项目根目录 (用于路径解析)

        Returns:
            HTML img 标签字符串，如果 local_path 无效则返回带占位符的标签
        """
        # 确保 src 有有效值
        src_path = self.local_path or self.original_url or f"missing-asset-{self.id}"

        # SOTA: 优先使用新型相对路径计算逻辑
        if target_file:
            abs_asset = self.get_absolute_path(workspace_path=workspace_path, project_root=project_root)
            if abs_asset:
                target_dir = Path(target_file).resolve().parent
                try:
                    src_path = os.path.relpath(abs_asset, target_dir)
                    
                    # 物理存在性校验 (Strict Mode)
                    if not abs_asset.exists():
                        warning = f"<!-- ⚠️ FILE MISSING: {src_path} (ID: {self.id}) -->"
                        # 如果文件丢失，我们仍然返回标签但附带警告
                        # 或者按 spec 要求返回特定占位符
                        return f"{warning}\n<img src=\"{src_path}\" alt=\"FILE MISSING\" data-asset-id=\"{self.id}\">"
                except ValueError:
                    pass
        elif md_subdir and src_path and not src_path.startswith(("http://", "https://", "/")):
            # 如果指定了 md_subdir，调整相对路径 (保持旧逻辑兼容性)
            if src_path.startswith("generated_assets/"):
                # workspace 内的生成资产: ../generated_assets/xxx
                src_path = f"../{src_path}"
            elif src_path.startswith("assets/"):
                # 项目根目录的资产: ../../../assets/xxx (workspaces/workspace/job_id/md → project_root)
                src_path = f"../../../{src_path}"
            elif not src_path.startswith("../"):
                # 其他 workspace 内的相对路径
                src_path = f"../{src_path}"

        parts = [f'<img src="{src_path}"']

        # Alt text
        alt = self.alt_text or self.semantic_label
        parts.append(f'alt="{alt}"')

        # Inline style with crop metadata
        style = self.crop_metadata.to_inline_style()
        parts.append(f'style="{style}"')

        # Optional class
        if class_name:
            parts.append(f'class="{class_name}"')

        # Data attributes for tracking
        parts.append(f'data-asset-id="{self.id}"')

        return " ".join(parts) + ">"

    def increment_usage(self, section_id: str) -> None:
        """记录资产使用"""
        self.usage_count += 1
        if section_id not in self.used_in_sections:
            self.used_in_sections.append(section_id)

    def can_reuse(self) -> bool:
        """检查是否可复用"""
        if self.reuse_policy == ReusePolicy.NEVER:
            return False
        if self.reuse_policy == ReusePolicy.ONCE and self.usage_count > 0:
            return False
        return True

    def is_quality_acceptable(self, min_level: AssetQualityLevel = AssetQualityLevel.MEDIUM) -> bool:
        """
        检查质量是否达到最低要求

        Args:
            min_level: 最低可接受质量等级

        Returns:
            是否达标
        """
        quality_order = {
            AssetQualityLevel.HIGH: 3,
            AssetQualityLevel.MEDIUM: 2,
            AssetQualityLevel.LOW: 1,
            AssetQualityLevel.UNASSESSED: 2,  # 未评估按中等处理
        }
        return quality_order[self.quality_level] >= quality_order[min_level]

    def record_rejection(self, section_id: str, reason: str, suggested_action: AssetFulfillmentAction) -> None:
        """
        记录被拒绝使用

        Args:
            section_id: 章节 ID
            reason: 拒绝原因
            suggested_action: 建议的替代行动
        """
        self.rejection_history.append({
            "section_id": section_id,
            "reason": reason,
            "suggested_action": suggested_action.value
        })

    def to_candidate_summary(self) -> str:
        """
        生成候选资产摘要 (供 Writer 判断使用)

        返回格式适合注入到 Prompt 中
        """
        lines = [f"**{self.id}**: {self.semantic_label}"]
        lines.append(f"  - 来源: {self.source.value} | 质量: {self.quality_level.value}")
        if self.quality_notes:
            lines.append(f"  - 备注: {self.quality_notes}")
        if self.suitable_for:
            lines.append(f"  - 适用: {', '.join(self.suitable_for)}")
        if self.unsuitable_for:
            lines.append(f"  - 不适用: {', '.join(self.unsuitable_for)}")
        if self.local_path:
            # 显示从 md/ 目录可用的相对路径
            display_path = self.local_path
            if display_path.startswith("assets/"):
                # 项目根目录的资产: ../../../assets/xxx
                display_path = f"../../../{display_path}"
            elif display_path.startswith("generated_assets/"):
                # workspace 内的生成资产: ../generated_assets/xxx
                display_path = f"../{display_path}"
            elif not display_path.startswith(("http://", "https://", "/", "../")):
                # 其他相对路径
                display_path = f"../{display_path}"
            lines.append(f"  - 路径: {display_path}")
        return "\n".join(lines)


class VisualIntentDeclaration(BaseModel):
    """
    视觉意图声明 - Writer 在创作时声明的图像需求

    Writer 输出此结构来表达：
    1. 需要什么样的图像
    2. 是否找到了合适的现有资产
    3. 如果没有，希望采取什么行动
    """
    intent_id: str = Field(..., description="意图 ID (如 's1-visual-1')")
    description: str = Field(..., description="图像内容描述 (用于搜图或生成)")
    context: str = Field(..., description="上下文说明 (为什么需要这张图)")
    placement: str = Field(default="inline", description="放置位置: inline, figure, hero, sidebar")

    # Writer 的决策
    action: AssetFulfillmentAction = Field(..., description="履约动作")
    matched_asset_id: Optional[str] = Field(default=None, description="匹配的现有资产 ID (若 action=USE_EXISTING)")
    rejection_reason: Optional[str] = Field(default=None, description="拒绝现有资产的原因 (若有)")

    # 生成/搜索参数
    svg_spec: Optional[str] = Field(default=None, description="SVG 生成规格 (若 action=GENERATE_SVG)")
    search_queries: list[str] = Field(default_factory=list, description="搜图关键词 (若 action=SEARCH_WEB)")
    mermaid_code: Optional[str] = Field(default=None, description="Mermaid 代码 (若 action=GENERATE_MERMAID)")

    # 裁切建议
    suggested_crop: Optional[CropMetadata] = Field(default=None, description="建议的裁切参数")

    def to_visual_directive(self) -> str:
        """
        生成 :::visual 指令块

        用于 Writer 输出中表示"需要新资产"的情况
        """
        config = {
            "id": self.intent_id,
            "action": self.action.value,
            "description": self.description,
        }

        if self.matched_asset_id:
            config["matched_asset"] = self.matched_asset_id
        if self.rejection_reason:
            config["rejection_reason"] = self.rejection_reason
        if self.search_queries:
            config["search_queries"] = self.search_queries
        if self.svg_spec:
            config["svg_spec"] = self.svg_spec
        if self.mermaid_code:
            config["mermaid_code"] = self.mermaid_code

        import json
        json_str = json.dumps(config, ensure_ascii=False)
        return f":::visual {json_str}\n{self.context}\n:::"


class UniversalAssetRegistry(BaseModel):
    """
    统一资产注册表 (UAR) - 系统的"视觉大脑" (SOTA 2.0 升级版)
    """
    # 核心资产池 (当前 Session 产出)
    assets: dict[str, AssetEntry] = Field(default_factory=dict, description="当前 Session 资产映射表")
    
    # 挂载的外部库 {workspace_name: {asset_id: AssetEntry}}
    mounted_workspaces: dict[str, dict[str, AssetEntry]] = Field(default_factory=dict)
    
    # 白名单 (允许在本项目中复用的外部资产 ID)
    whitelisted_ids: set[str] = Field(default_factory=set)
    
    # 用户强制提供的资产 ID (inputs/ 目录)
    user_provided_ids: set[str] = Field(default_factory=set)

    # SOTA Fix: 使用正式字段而非私有属性，确保在序列化过程中不丢失持久化路径
    persist_path: Optional[str] = Field(default=None, description="UAR 持久化路径")
    
    # SOTA Fix: 将 stats 变为正式字段，确保报表准确
    stats: dict = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    def set_persist_path(self, path: str) -> None:
        """设置持久化路径 (通常是当前 workspaces/workspace/assets.json)"""
        self.persist_path = path

    def mount_workspace(self, name: str, assets_json_path: str) -> bool:
        """挂载一个外部资产库"""
        path = Path(assets_json_path)
        if not path.exists():
            return False
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ws_assets = {}
            for aid, adata in data.get("assets", {}).items():
                # 兼容性处理
                if "crop_metadata" in adata and adata["crop_metadata"]:
                    adata["crop_metadata"] = CropMetadata(**adata["crop_metadata"])
                ws_assets[aid] = AssetEntry(**adata)
            
            self.mounted_workspaces[name] = ws_assets
            return True
        except Exception as e:
            print(f"  [UAR] 挂载失败 {name}: {e}")
            return False

    def add_to_whitelist(self, asset_id: str) -> None:
        """将资产加入本项目白名单"""
        self.whitelisted_ids.add(asset_id)

    def get_assets_by_source(self, source: AssetSource) -> list[AssetEntry]:
        """根据来源获取资产列表 (仅限当前 Session)"""
        return [a for a in self.assets.values() if a.source == source]

    def get_reusable_assets(self) -> list[AssetEntry]:
        """获取所有可复用的资产 (仅限当前 Session)"""
        return [a for a in self.assets.values() if a.can_reuse()]

    def register_immediate(self, entry: AssetEntry) -> None:
        """注册当前 Session 产出的资产"""
        self.assets[entry.id] = entry
        self._persist()

    def register_batch(self, entries: list[AssetEntry]) -> None:
        """批量注册资产并执行单次持久化 (SOTA Parallel Optimization)"""
        if not entries:
            return
        print(f"  [UAR] 🚀 正在批量注册 {len(entries)} 个新资产...")
        for entry in entries:
            self.assets[entry.id] = entry
        self._persist()

    def get_asset(self, asset_id: str) -> Optional[AssetEntry]:
        """全局查找资产 (Session -> Mounted)"""
        if asset_id in self.assets:
            return self.assets[asset_id]
        
        for ws in self.mounted_workspaces.values():
            if asset_id in ws:
                return ws[asset_id]
        return None

    def get_all_candidates(self) -> list[AssetEntry]:
        """
        获取所有可用于复用的候选资产。
        优先级权重将在 Prompt 中处理，此处返回：
        1. 本次 Session 产出的所有资产 (Free to use)
        2. 用户提供的输入资产 (Mandatory)
        3. 被选入白名单的挂载库资产
        """
        candidates = []
        
        # 1. Session 资产 (含用户输入的)
        candidates.extend(self.assets.values())
        
        # 2. 挂载库中处于白名单的资产
        for ws_assets in self.mounted_workspaces.values():
            for aid, asset in ws_assets.items():
                if aid in self.whitelisted_ids and aid not in self.assets:
                    candidates.append(asset)
        
        return candidates

    def generate_id(self, namespace: str, semantic_hint: str) -> str:
        """
        生成唯一资产 ID

        格式: {namespace}-{semantic_slug}-{hash_suffix}
        示例: s1-ecg-pwave-a3f2
        """
        # 简化语义提示为 slug
        slug = semantic_hint.lower()[:20].replace(" ", "-").replace("_", "-")
        # 生成短哈希后缀
        hash_input = f"{namespace}-{semantic_hint}-{len(self.assets)}"
        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:4]
        return f"{namespace}-{slug}-{hash_suffix}"

    def _persist(self) -> None:
        """持久化到 JSON 文件"""
        if not self.persist_path:
            return

        path = Path(self.persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # SOTA: 动态刷新统计信息
        self.stats = {
            "by_source": {
                s.value: len([a for a in self.assets.values() if a.source == s])
                for s in AssetSource
            },
            "reusable_count": len(self.get_reusable_assets())
        }

        # 序列化所有资产
        data = {
            "assets": {k: (v.model_dump() if hasattr(v, 'model_dump') else v.dict()) for k, v in self.assets.items()},
            "total_count": len(self.assets),
            "stats": self.stats
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  [UAR] 💾 成功持久化 {len(self.assets)} 个资产至 {path.name}")

    @classmethod
    def load_from_file(cls, path: str) -> "UniversalAssetRegistry":
        """从 JSON 文件加载 UAR"""
        registry = cls()
        registry.set_persist_path(path)

        file_path = Path(path)
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for asset_id, asset_data in data.get("assets", {}).items():
                # 处理枚举类型（带默认值，兼容旧版 assets.json）
                asset_data["source"] = AssetSource(asset_data.get("source", "USER"))
                asset_data["vqa_status"] = AssetVQAStatus(asset_data.get("vqa_status", "PENDING"))
                asset_data["reuse_policy"] = ReusePolicy(asset_data.get("reuse_policy", "ALWAYS"))
                # SOTA 2.0: 质量等级枚举
                if "quality_level" in asset_data and asset_data["quality_level"]:
                    asset_data["quality_level"] = AssetQualityLevel(asset_data["quality_level"])
                else:
                    asset_data["quality_level"] = AssetQualityLevel.UNASSESSED
                # 处理嵌套模型
                if "crop_metadata" in asset_data and asset_data["crop_metadata"]:
                    asset_data["crop_metadata"] = CropMetadata(**asset_data["crop_metadata"])
                registry.assets[asset_id] = AssetEntry(**asset_data)
            
            # 加载已有的统计信息
            registry.stats = data.get("stats", {})

        return registry

    async def intent_match_candidates_async(self, query: str, client: Any, limit: int = 5) -> list[AssetEntry]:
        """
        使用 VLM (Gemini Flash) 对本地资产池进行语义粗筛
        """
        all_candidates = self.get_all_candidates()
        if not all_candidates:
            return []

        # 构造资产列表摘要
        catalog = []
        for asset in all_candidates:
            catalog.append({
                "id": asset.id,
                "label": asset.semantic_label,
                "tags": asset.tags
            })

        prompt = f"""你是一位视觉资产检索专家。请根据用户的创作意图，从资产目录中筛选出最相关的 **Top {limit}** 个资产。

### 用户创作意图
{query}

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
            response = await client.generate_async(
                prompt=prompt,
                system_instruction="你是一位专业的资产检索助手。请快速准确地筛选相关资产。",
                temperature=0.0,
                stream=True
            )
            
            if response.success:
                import re
                match = re.search(r'\{[\s\S]*\}', response.text)
                if match:
                    data = json.loads(match.group())
                    suggestion_ids = data.get("suggestions", [])
                    
                    # 按照返回的顺序查找并返回 AssetEntry
                    result = []
                    for aid in suggestion_ids:
                        asset = self.get_asset(aid)
                        if asset:
                            result.append(asset)
                    return result[:limit]
            return []
        except Exception as e:
            print(f"  [UAR] 语义匹配失败: {e}")
            return []

    def intent_match_candidates(self, query: str, client: Any, limit: int = 5) -> list[AssetEntry]:
        """同步版本 (封装异步调用)"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # 如果已经在运行的事件循环中，使用 thread pool 或者直接 run (虽然不推荐在 async 中调用同步封装)
                return [] # 这种情况下应直接调用 _async 版本
            return asyncio.run(self.intent_match_candidates_async(query, client, limit))
        except RuntimeError:
            return asyncio.run(self.intent_match_candidates_async(query, client, limit))

    def to_summary(self, include_quality: bool = True) -> str:
        """
        生成资产注册表摘要 (用于 Prompt 注入)

        Args:
            include_quality: 是否包含质量评估信息
        """
        lines = ["## 📦 可用资产注册表 (UAR)", ""]
        lines.append("以下是可用的图像资产。请根据写作需求判断是否使用，如果质量不佳或不符合意图，可以选择生成 SVG 或启用网络搜图。\n")

        reusable = self.get_reusable_assets()
        if not reusable:
            lines.append("*当前无可复用资产，请使用 `:::visual` 指令声明图像需求*")
            return "\n".join(lines)

        for asset in reusable:
            lines.append(asset.to_candidate_summary())
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def to_decision_context(self, visual_intent: str, client: Any) -> str:
        """
        生成针对特定视觉意图的决策上下文

        Args:
            visual_intent: 视觉意图描述 (如 "心电图 P 波形成过程")
            client: Gemini 客户端

        Returns:
            包含候选资产和决策指导的 Prompt 片段
        """
        lines = [f"### 🎯 视觉需求: {visual_intent}", ""]
        lines.append("**可用候选资产:**")

        candidates = self.intent_match_candidates(visual_intent, client=client, limit=5)
        if not candidates:
            lines.append("*无匹配的现有资产*")
            lines.append("")
            lines.append("**建议行动:** 使用 `:::visual` 指令，指定 `action: GENERATE_SVG` 或 `action: SEARCH_WEB`")
        else:
            for i, asset in enumerate(candidates, 1):
                lines.append(f"\n**候选 {i}:**")
                lines.append(asset.to_candidate_summary())

            lines.append("")
            lines.append("**决策指导:**")
            lines.append("- 如果候选资产质量高且符合意图 → 直接使用 `<img>` 标签 (action: USE_EXISTING)")
            lines.append("- 如果候选资产质量不佳 → 使用 `:::visual` 并说明拒绝原因")
            lines.append("- 如果需要精确的示意图 → 建议 action: GENERATE_SVG")
            lines.append("- 如果需要真实照片/复杂图像 → 建议 action: SEARCH_WEB")

        return "\n".join(lines)


# ============================================================================
# 原有模型 (保持不变)
# ============================================================================


class SectionInfo(BaseModel):
    """章节信息"""
    id: str = Field(..., description="章节唯一标识符，例如 sec-1")
    title: str = Field(..., description="章节标题")
    summary: str = Field(..., description="章节摘要")
    estimated_words: int = Field(default=0, description="预估字数")
    file_path: Optional[str] = Field(default=None, description="Markdown 文件路径")
    metadata: dict = Field(default_factory=dict, description="章节元数据 (辅助后续 Agent 处理，如 layout, style 等)")


class Manifest(BaseModel):
    """项目清单 - 由架构师 Agent 生成"""
    project_title: str = Field(..., description="项目标题")
    author: Optional[str] = Field(default=None, description="作者")
    description: str = Field(..., description="项目描述")
    sections: list[SectionInfo] = Field(default_factory=list, description="章节列表")
    metadata: dict = Field(default_factory=dict, description="全局元数据")
    config: dict = Field(default_factory=dict, description="项目配置 (如全局布局偏好等)")
    knowledge_map: dict[str, list[str]] = Field(
        default_factory=dict, 
        description="核心知识点映射，key 为章节 ID，value 为知识点列表"
    )
    
    def get_section_by_id(self, section_id: str) -> Optional[SectionInfo]:
        """根据 ID 获取章节"""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None


class DesignTokens(BaseModel):
    """设计令牌 - 视觉设计决策的单一真理来源 (SOTA Design System Pattern)"""
    colors: dict = Field(default_factory=dict, description="颜色令牌 (primitive + semantic)")
    typography: dict = Field(default_factory=dict, description="排版令牌 (font-family, size, weight, line-height)")
    spacing: dict = Field(default_factory=dict, description="间距令牌")
    effects: dict = Field(default_factory=dict, description="效果令牌 (shadows, border-radius, blur)")
    components: dict = Field(default_factory=dict, description="组件令牌 (card, button, callout 等)")
    raw_json: dict = Field(default_factory=dict, description="原始 JSON 数据")
    
    def get_css_variables(self) -> str:
        """生成 CSS 变量声明"""
        lines = [":root {"]
        
        # Colors - primitive
        for key, value in self.colors.get("primitive", {}).items():
            lines.append(f"  --color-{key}: {value};")
        
        # Colors - semantic
        for key, value in self.colors.get("semantic", {}).items():
            # Handle token references like {colors.primitive.blue-500}
            if isinstance(value, str) and value.startswith("{"):
                # For now, just use the raw value; CSS generation will resolve
                pass
            lines.append(f"  --color-{key}: {value};")
        
        # Typography
        for category, values in self.typography.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    lines.append(f"  --{category}-{key}: {value};")
        
        # Spacing
        for key, value in self.spacing.items():
            lines.append(f"  --spacing-{key}: {value};")
        
        # Effects
        for category, values in self.effects.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    lines.append(f"  --{category}-{key}: {value};")
        
        lines.append("}")
        return "\n".join(lines)


class StyleRule(BaseModel):
    """样式规则"""
    markdown_pattern: str = Field(..., description="Markdown 模式标识")
    css_selector: str = Field(..., description="对应的 CSS 选择器/类名")
    description: Optional[str] = Field(default=None, description="规则描述")


class StyleMapping(BaseModel):
    """样式契约 - 由设计师 Agent 生成"""
    rules: list[StyleRule] = Field(default_factory=list, description="样式规则列表")
    
    def get_css_for_pattern(self, pattern: str) -> Optional[str]:
        """根据 Markdown 模式获取 CSS 选择器"""
        for rule in self.rules:
            if rule.markdown_pattern == pattern:
                return rule.css_selector
        return None
    
    def to_dict(self) -> dict[str, str]:
        """转换为简单字典格式"""
        return {rule.markdown_pattern: rule.css_selector for rule in self.rules}


class AgentState(BaseModel):
    """LangGraph Agent 状态"""
    job_id: str = Field(..., description="任务 ID")
    workspace_path: str = Field(..., description="工作目录路径")
    
    # 输入 (SOTA 2.0: 严格分离用户意图与参考资料)
    user_intent: str = Field(default="", description="用户意图/指令 (告诉 AI 做什么)")
    reference_materials: str = Field(default="", description="参考资料全文 (知识/数据，供创作参考)")
    project_brief: str = Field(default="", description="经过 Refine 的项目需求书")
    images: list[dict] = Field(default_factory=list, description="图片素材 (base64 encoded inlineData)")
    reference_doc_paths: list[str] = Field(default_factory=list, description="参考资料文件路径列表 (仅用于追踪)")
    
    # 数据契约
    manifest: Optional[Manifest] = Field(default=None, description="项目清单")
    design_tokens: Optional[DesignTokens] = Field(default=None, description="设计令牌 (SOTA 单一真理来源)")
    style_mapping: Optional[StyleMapping] = Field(default=None, description="样式契约")

    # SOTA 2.0: 统一资产注册表
    asset_registry: Optional[UniversalAssetRegistry] = Field(default=None, description="统一资产注册表 (UAR)")
    uar_path: Optional[str] = Field(default=None, description="UAR 持久化路径 (assets.json)")
    
    # 进度跟踪
    current_section_index: int = Field(default=0, description="当前处理的章节索引")
    completed_md_sections: list[str] = Field(default_factory=list, description="已完成的 Markdown 章节路径")
    completed_html_sections: list[str] = Field(default_factory=list, description="已完成的 HTML 片段路径")
    
    # 设计资产
    css_path: Optional[str] = Field(default=None, description="CSS 文件路径")
    js_path: Optional[str] = Field(default=None, description="JS 文件路径")
    
    # 最终输出
    final_html_path: Optional[str] = Field(default=None, description="最终 HTML 文件路径")
    
    # Reasoning
    thoughts: str = Field(default="", description="AI 推理过程 (Thinking tokens)")

    # 错误处理
    errors: list[str] = Field(default_factory=list, description="错误日志")
    
    # Human-in-the-Loop fields
    clarifier_questions: list[dict] = Field(default_factory=list, description="Clarifier 生成的问题列表")
    clarifier_answers: dict[str, str] = Field(default_factory=dict, description="用户对问题的回答")
    user_brief_feedback: Optional[str] = Field(default=None, description="用户对 Brief 的修改意见")
    user_outline_feedback: Optional[str] = Field(default=None, description="用户对大纲的修改意见")
    brief_approved: bool = Field(default=False, description="Brief 是否通过审核")
    outline_approved: bool = Field(default=False, description="大纲是否通过审核")
    asset_approved: bool = Field(default=False, description="资产履约是否通过审核")
    vqa_iterations: int = Field(default=0, description="Visual QA 迭代次数")
    vqa_needs_reassembly: bool = Field(default=False, description="是否需要重新拼装")
    md_qa_iterations: int = Field(default=0, description="Markdown QA 迭代次数")
    md_qa_needs_revision: bool = Field(default=False, description="是否需要 MD 返工")
    
    # Loop-specific metadata (e.g. retry flags, hashes)
    loop_metadata: dict[str, Any] = Field(default_factory=dict, description="循环相关的元数据（如重试标志）")

    # SOTA 2.0: 资产履约修复
    batch_fulfillment_complete: bool = Field(default=False, description="全书批量履约是否完成")
    failed_directives: list[dict] = Field(default_factory=list, description="履约失败的指令列表")
    asset_revision_needed: bool = Field(default=False, description="是否需要人工干预修复资产")
    failed_asset_id: Optional[str] = Field(default=None, description="失败的资产 ID")

    rewrite_needed: bool = Field(default=False, description="是否需要触发重写逻辑")
    rewrite_feedback: str = Field(default="", description="重写反馈意见")
    skip_markdown_qa: bool = Field(default=False, description="是否跳过 Markdown QA (默认为 False)")
    markdown_approved: bool = Field(default=False, description="Markdown 是否通过人机审核")
    user_markdown_feedback: Optional[str] = Field(default=None, description="用户对 Markdown 的修改意见")
    debug_mode: bool = Field(default=False, description="是否开启调试模式，开启后将保存每一步的状态")
    auto_mode: bool = Field(default=False, description="是否开启自动模式 (绕过 HITL)")
    
    def is_manifest_ready(self) -> bool:
        """检查清单是否就绪"""
        return self.manifest is not None
    
    def is_design_ready(self) -> bool:
        """检查设计资产是否就绪"""
        return (
            self.style_mapping is not None 
            and self.css_path is not None 
            and self.js_path is not None
        )
    
    def all_sections_written(self) -> bool:
        """检查所有章节是否已写完 Markdown"""
        if not self.manifest:
            return False
        return len(self.completed_md_sections) >= len(self.manifest.sections)
    
    def all_sections_transformed(self) -> bool:
        """检查所有章节是否已转换为 HTML"""
        if not self.manifest:
            return False
        return len(self.completed_html_sections) >= len(self.manifest.sections)

    @property
    def user_context(self) -> str:
        """
        用户意图上下文 (Context Chain / Residual Connection)
        
        关键规划节点应注入此上下文：
        - Clarifier, Refiner, Architect, TechSpec, DesignTokens
        
        执行节点 (Writer, Transformer, Critic) 不需要直接注入，
        它们使用关键节点的产出 (manifest, design_tokens 等)
        """
        parts = []
        
        # 1. User Intent (instruction from user)
        if self.user_intent:
            parts.append(f"# 🎯 用户意图 (Instruction)\n{self.user_intent}")
        
        # 2. Clarification Q&A (if answered)
        if self.clarifier_questions and self.clarifier_answers:
            qa_lines = ["# ❓ 用户澄清问答"]
            for q in self.clarifier_questions:
                qid = q.get('id', '')
                question = q.get('question', '')
                answer = self.clarifier_answers.get(qid, '(未回答)')
                qa_lines.append(f"- Q [{q.get('category', '')}]: {question}")
                qa_lines.append(f"  A: {answer}")
            parts.append("\n".join(qa_lines))
        
        # 3. Approved Brief (if exists)
        if self.project_brief:
            parts.append(f"# 📝 已审核的项目简报\n{self.project_brief}")

        return "\n\n---\n\n".join(parts) if parts else ""

    # ========================================================================
    # SOTA 2.0: 资产管理与全量上下文
    # ========================================================================

    def initialize_uar(self) -> UniversalAssetRegistry:
        """
        初始化或加载 UAR

        如果 uar_path 存在，从文件加载；否则创建新的 UAR
        """
        if self.asset_registry is not None:
            return self.asset_registry

        # 设置默认 UAR 路径
        if not self.uar_path:
            self.uar_path = f"{self.workspace_path}/assets.json"

        # 加载或创建 UAR
        self.asset_registry = UniversalAssetRegistry.load_from_file(self.uar_path)
        return self.asset_registry

    def get_uar(self) -> UniversalAssetRegistry:
        """获取 UAR (如果不存在则初始化)"""
        if self.asset_registry is None:
            return self.initialize_uar()
        return self.asset_registry

    def get_completed_sections_content(self) -> str:
        """
        获取已完成章节的全量内容 (用于全量上下文注入)

        返回格式:
        # 章节 1: 标题
        [Markdown 内容]

        # 章节 2: 标题
        [Markdown 内容]
        ...
        """
        if not self.manifest or not self.completed_md_sections:
            return ""

        parts = []
        for i, section in enumerate(self.manifest.sections):
            if i >= len(self.completed_md_sections):
                break

            md_path = self.completed_md_sections[i]
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                parts.append(f"# 章节 {i+1}: {section.title}\n\n{content}")
            except FileNotFoundError:
                parts.append(f"# 章节 {i+1}: {section.title}\n\n*[文件未找到: {md_path}]*")

        return "\n\n---\n\n".join(parts)

    @property
    def full_creation_context(self) -> str:
        """
        全量创作上下文 (Full-Context Perception)

        供 Writer Agent 使用，包含:
        1. 完整规划 (Manifest)
        2. 提炼后的意图 (Brief)
        3. 用户意图 (User Intent)
        4. 参考资料全文 (Reference Materials)
        5. 资产注册表摘要 (UAR Summary)
        6. 已完成章节内容

        注意: Vision Part (图像素材) 需要单独通过 multimodal 方式注入
        """
        parts = []

        # 1. 项目规划
        if self.manifest:
            manifest_summary = f"""## 📋 项目规划 (Manifest)
**标题**: {self.manifest.project_title}
**描述**: {self.manifest.description}

### 章节结构
"""
            for i, sec in enumerate(self.manifest.sections):
                status = "✅" if i < len(self.completed_md_sections) else "⏳"
                manifest_summary += f"{status} {sec.id}: {sec.title} (~{sec.estimated_words}字)\n"
                manifest_summary += f"   摘要: {sec.summary[:100]}...\n"
            parts.append(manifest_summary)

        # 2. 项目简报
        if self.project_brief:
            parts.append(f"## 📝 项目简报 (Brief)\n\n{self.project_brief}")

        # 3. 用户意图
        if self.user_intent:
            parts.append(f"## 🎯 用户意图\n\n{self.user_intent}")

        # 4. 参考资料全文
        if self.reference_materials:
            parts.append(f"## 📚 参考资料\n\n{self.reference_materials}")

        # 5. UAR 摘要
        if self.asset_registry:
            parts.append(self.asset_registry.to_summary())

        # 6. 已完成章节
        completed_content = self.get_completed_sections_content()
        if completed_content:
            parts.append(f"## ✍️ 已完成章节\n\n{completed_content}")

        return "\n\n---\n\n".join(parts) if parts else ""

    def get_current_section_namespace(self) -> str:
        """获取当前章节的命名空间前缀"""
        return f"s{self.current_section_index + 1}"

