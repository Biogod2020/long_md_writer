"""
Persistence: SOTA 2.0 Phase C 实验管理与 Profile 持久化

核心职责：
1. ProjectProfile - 项目快照系统，支持实验复现
2. Profile 重装载 - 一键恢复实验状态
3. 资产决策链追踪 - 记录资产产生的驱动意图

使用场景：
- 实验复现：通过 --profile <id> 恢复特定运行状态
- 控制变量实验：只修改部分章节，复用其他配置
- 资产审计：追踪每个资产的产生原因
"""

import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from .types import AgentState, Manifest


# ============================================================================
# Profile 数据模型
# ============================================================================

class ProfileStatus(Enum):
    """Profile 状态"""
    ACTIVE = "active"  # 正在运行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 运行失败
    ARCHIVED = "archived"  # 已归档


@dataclass
class PromptSnapshot:
    """提示词快照"""
    agent_name: str
    system_instruction: str
    user_prompt_template: str
    parameters: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PromptSnapshot":
        return cls(**data)


@dataclass
class InputBlueprint:
    """输入蓝图 - 记录原始数据的路径和版本"""
    raw_materials_path: str
    raw_materials_hash: str  # 内容哈希，用于检测变化
    user_prompt_path: str
    user_prompt_hash: str
    assets_dir: str
    asset_files: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InputBlueprint":
        return cls(**data)


@dataclass
class UARCheckpoint:
    """UAR 检查点 - 存储资产状态和裁切决策"""
    assets: list[dict] = field(default_factory=list)
    decision_chain: list[dict] = field(default_factory=list)  # 决策链
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "assets": self.assets,
            "decision_chain": self.decision_chain,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UARCheckpoint":
        return cls(
            assets=data.get("assets", []),
            decision_chain=data.get("decision_chain", []),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class AssetDecision:
    """资产决策记录 - 追踪资产产生的驱动意图"""
    asset_id: str
    action: str  # USE_EXISTING, GENERATE_SVG, SEARCH_WEB, etc.
    source: str  # USER, AI, WEB
    driving_intent: str  # 驱动产生该资产的用户意图
    section_id: str  # 所属章节
    context: str  # 上下文描述
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AssetDecision":
        return cls(**data)


@dataclass
class ProjectProfile:
    """
    项目 Profile - 完整的实验快照

    包含：
    - 元数据（ID、时间、状态）
    - 提示词快照
    - 输入蓝图
    - UAR 检查点
    - Manifest 副本
    - 已完成章节
    """
    profile_id: str
    project_title: str
    status: ProfileStatus = ProfileStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 快照数据
    prompts: list[PromptSnapshot] = field(default_factory=list)
    input_blueprint: Optional[InputBlueprint] = None
    uar_checkpoint: Optional[UARCheckpoint] = None
    manifest: Optional[dict] = None
    completed_sections: dict = field(default_factory=dict)  # section_id -> content

    # 元信息
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "project_title": self.project_title,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "prompts": [p.to_dict() for p in self.prompts],
            "input_blueprint": self.input_blueprint.to_dict() if self.input_blueprint else None,
            "uar_checkpoint": self.uar_checkpoint.to_dict() if self.uar_checkpoint else None,
            "manifest": self.manifest,
            "completed_sections": self.completed_sections,
            "notes": self.notes,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectProfile":
        return cls(
            profile_id=data["profile_id"],
            project_title=data["project_title"],
            status=ProfileStatus(data.get("status", "active")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            prompts=[PromptSnapshot.from_dict(p) for p in data.get("prompts", [])],
            input_blueprint=InputBlueprint.from_dict(data["input_blueprint"]) if data.get("input_blueprint") else None,
            uar_checkpoint=UARCheckpoint.from_dict(data["uar_checkpoint"]) if data.get("uar_checkpoint") else None,
            manifest=data.get("manifest"),
            completed_sections=data.get("completed_sections", {}),
            notes=data.get("notes", ""),
            tags=data.get("tags", [])
        )


# ============================================================================
# Profile 管理器
# ============================================================================

class ProfileManager:
    """
    Profile 管理器

    负责创建、保存、加载和管理项目 Profiles
    """

    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        初始化 Profile 管理器

        Args:
            profiles_dir: Profiles 存储目录，默认为 workspace/profiles
        """
        self.profiles_dir = profiles_dir or Path("workspace/profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._current_profile: Optional[ProjectProfile] = None

    @property
    def current_profile(self) -> Optional[ProjectProfile]:
        """获取当前活动的 Profile"""
        return self._current_profile

    def create_profile(
        self,
        project_title: str,
        profile_id: Optional[str] = None,
        tags: list[str] = None
    ) -> ProjectProfile:
        """
        创建新的 Profile

        Args:
            project_title: 项目标题
            profile_id: 自定义 Profile ID（可选）
            tags: 标签列表

        Returns:
            新创建的 ProjectProfile
        """
        if profile_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            profile_id = f"profile_{timestamp}"

        profile = ProjectProfile(
            profile_id=profile_id,
            project_title=project_title,
            tags=tags or []
        )

        self._current_profile = profile
        self._ensure_profile_dir(profile_id)
        self.save_profile(profile)

        print(f"[ProfileManager] 创建 Profile: {profile_id}")
        return profile

    def load_profile(self, profile_id: str) -> Optional[ProjectProfile]:
        """
        加载已有的 Profile

        Args:
            profile_id: Profile ID

        Returns:
            加载的 ProjectProfile 或 None
        """
        profile_path = self.profiles_dir / profile_id / "profile.json"

        if not profile_path.exists():
            print(f"[ProfileManager] Profile 不存在: {profile_id}")
            return None

        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            profile = ProjectProfile.from_dict(data)
            self._current_profile = profile
            print(f"[ProfileManager] 加载 Profile: {profile_id}")
            return profile
        except Exception as e:
            print(f"[ProfileManager] 加载 Profile 失败: {e}")
            return None

    def save_profile(self, profile: Optional[ProjectProfile] = None) -> bool:
        """
        保存 Profile

        Args:
            profile: 要保存的 Profile，默认为当前 Profile

        Returns:
            是否保存成功
        """
        profile = profile or self._current_profile
        if profile is None:
            print("[ProfileManager] 没有活动的 Profile")
            return False

        profile.updated_at = datetime.now().isoformat()
        profile_dir = self._ensure_profile_dir(profile.profile_id)

        try:
            # 保存主 profile.json
            profile_path = profile_dir / "profile.json"
            profile_path.write_text(
                json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            # 分别保存各个快照文件（便于单独查看）
            if profile.prompts:
                prompts_path = profile_dir / "prompts_snapshot.json"
                prompts_path.write_text(
                    json.dumps([p.to_dict() for p in profile.prompts], indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

            if profile.input_blueprint:
                blueprint_path = profile_dir / "input_blueprint.json"
                blueprint_path.write_text(
                    json.dumps(profile.input_blueprint.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

            if profile.uar_checkpoint:
                uar_path = profile_dir / "uar_checkpoint.json"
                uar_path.write_text(
                    json.dumps(profile.uar_checkpoint.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

            return True

        except Exception as e:
            print(f"[ProfileManager] 保存 Profile 失败: {e}")
            return False

    def list_profiles(self) -> list[dict]:
        """
        列出所有 Profiles

        Returns:
            Profile 摘要列表
        """
        profiles = []

        for profile_dir in self.profiles_dir.iterdir():
            if profile_dir.is_dir():
                profile_path = profile_dir / "profile.json"
                if profile_path.exists():
                    try:
                        data = json.loads(profile_path.read_text(encoding="utf-8"))
                        profiles.append({
                            "profile_id": data.get("profile_id"),
                            "project_title": data.get("project_title"),
                            "status": data.get("status"),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "tags": data.get("tags", [])
                        })
                    except Exception:
                        pass

        # 按更新时间排序
        profiles.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return profiles

    def delete_profile(self, profile_id: str) -> bool:
        """
        删除 Profile

        Args:
            profile_id: Profile ID

        Returns:
            是否删除成功
        """
        profile_dir = self.profiles_dir / profile_id

        if not profile_dir.exists():
            return False

        try:
            shutil.rmtree(profile_dir)
            if self._current_profile and self._current_profile.profile_id == profile_id:
                self._current_profile = None
            print(f"[ProfileManager] 删除 Profile: {profile_id}")
            return True
        except Exception as e:
            print(f"[ProfileManager] 删除 Profile 失败: {e}")
            return False

    def archive_profile(self, profile_id: str) -> bool:
        """
        归档 Profile

        Args:
            profile_id: Profile ID

        Returns:
            是否归档成功
        """
        profile = self.load_profile(profile_id)
        if profile:
            profile.status = ProfileStatus.ARCHIVED
            return self.save_profile(profile)
        return False

    def _ensure_profile_dir(self, profile_id: str) -> Path:
        """确保 Profile 目录存在"""
        profile_dir = self.profiles_dir / profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    # ========================================================================
    # 快照记录方法
    # ========================================================================

    def record_prompt(
        self,
        agent_name: str,
        system_instruction: str,
        user_prompt_template: str,
        parameters: dict = None
    ):
        """记录提示词快照"""
        if self._current_profile is None:
            return

        snapshot = PromptSnapshot(
            agent_name=agent_name,
            system_instruction=system_instruction,
            user_prompt_template=user_prompt_template,
            parameters=parameters or {}
        )
        self._current_profile.prompts.append(snapshot)

    def record_input_blueprint(
        self,
        raw_materials_path: str,
        raw_materials_content: str,
        user_prompt_path: str,
        user_prompt_content: str,
        assets_dir: str,
        asset_files: list[str] = None,
        parameters: dict = None
    ):
        """记录输入蓝图"""
        if self._current_profile is None:
            return

        self._current_profile.input_blueprint = InputBlueprint(
            raw_materials_path=raw_materials_path,
            raw_materials_hash=self._compute_hash(raw_materials_content),
            user_prompt_path=user_prompt_path,
            user_prompt_hash=self._compute_hash(user_prompt_content),
            assets_dir=assets_dir,
            asset_files=asset_files or [],
            parameters=parameters or {}
        )

    def record_uar_checkpoint(self, state: AgentState):
        """从 AgentState 记录 UAR 检查点"""
        if self._current_profile is None:
            return

        uar = state.get_uar()
        if uar is None:
            return

        assets_data = [
            {
                "id": a.id,
                "source": a.source.value,
                "semantic_label": a.semantic_label,
                "local_path": a.local_path,
                "quality_level": a.quality_level.value if a.quality_level else None,
                "crop_metadata": a.crop_metadata.dict() if a.crop_metadata else None
            }
            for a in uar.assets.values()
        ]

        self._current_profile.uar_checkpoint = UARCheckpoint(
            assets=assets_data,
            decision_chain=[]  # 决策链由 AssetService 管理
        )

    def record_manifest(self, manifest: Manifest):
        """记录 Manifest"""
        if self._current_profile is None:
            return

        self._current_profile.manifest = {
            "project_title": manifest.project_title,
            "description": manifest.description,
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "summary": s.summary,
                    "estimated_words": s.estimated_words,
                    "metadata": s.metadata
                }
                for s in manifest.sections
            ]
        }

    def record_completed_section(self, section_id: str, content: str):
        """记录已完成的章节"""
        if self._current_profile is None:
            return

        self._current_profile.completed_sections[section_id] = content

    def mark_completed(self):
        """标记 Profile 为已完成"""
        if self._current_profile:
            self._current_profile.status = ProfileStatus.COMPLETED
            self.save_profile()

    def mark_failed(self, error: str = ""):
        """标记 Profile 为失败"""
        if self._current_profile:
            self._current_profile.status = ProfileStatus.FAILED
            self._current_profile.notes = f"失败原因: {error}"
            self.save_profile()

    @staticmethod
    def _compute_hash(content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ============================================================================
# 资产服务
# ============================================================================

class AssetService:
    """
    资产服务

    提供资产管理和决策链追踪功能
    """

    def __init__(self, profile_manager: Optional[ProfileManager] = None):
        """
        初始化资产服务

        Args:
            profile_manager: Profile 管理器
        """
        self.profile_manager = profile_manager
        self._decisions: list[AssetDecision] = []

    def record_decision(
        self,
        asset_id: str,
        action: str,
        source: str,
        driving_intent: str,
        section_id: str,
        context: str = ""
    ):
        """
        记录资产决策

        Args:
            asset_id: 资产 ID
            action: 执行的操作
            source: 资产来源
            driving_intent: 驱动意图
            section_id: 所属章节
            context: 上下文
        """
        decision = AssetDecision(
            asset_id=asset_id,
            action=action,
            source=source,
            driving_intent=driving_intent,
            section_id=section_id,
            context=context
        )
        self._decisions.append(decision)

        # 同步到 Profile
        if self.profile_manager and self.profile_manager.current_profile:
            if self.profile_manager.current_profile.uar_checkpoint:
                self.profile_manager.current_profile.uar_checkpoint.decision_chain.append(
                    decision.to_dict()
                )

    def get_asset_dashboard(self, state: AgentState) -> dict:
        """
        获取资产看板数据

        Args:
            state: Agent 状态

        Returns:
            看板数据
        """
        uar = state.get_uar()
        if uar is None:
            return {
                "total": 0,
                "by_source": {},
                "by_quality": {},
                "reuse_rate": 0
            }

        assets = list(uar.assets.values())
        total = len(assets)

        # 按来源分类
        by_source = {}
        for asset in assets:
            source = asset.source.value
            by_source[source] = by_source.get(source, 0) + 1

        # 按质量分类
        by_quality = {}
        for asset in assets:
            if asset.quality_level:
                quality = asset.quality_level.value
                by_quality[quality] = by_quality.get(quality, 0) + 1

        # 计算复用率
        user_assets = by_source.get("USER", 0)
        reuse_rate = user_assets / total if total > 0 else 0

        return {
            "total": total,
            "by_source": by_source,
            "by_quality": by_quality,
            "reuse_rate": round(reuse_rate, 2),
            "decisions_count": len(self._decisions)
        }

    def get_decision_chain(self, asset_id: Optional[str] = None) -> list[dict]:
        """
        获取决策链

        Args:
            asset_id: 特定资产 ID（可选）

        Returns:
            决策记录列表
        """
        if asset_id:
            return [d.to_dict() for d in self._decisions if d.asset_id == asset_id]
        return [d.to_dict() for d in self._decisions]

    def get_section_assets(self, section_id: str) -> list[dict]:
        """
        获取章节的资产列表

        Args:
            section_id: 章节 ID

        Returns:
            资产决策列表
        """
        return [d.to_dict() for d in self._decisions if d.section_id == section_id]

    def export_report(self) -> dict:
        """
        导出资产报告

        Returns:
            完整的资产报告
        """
        return {
            "generated_at": datetime.now().isoformat(),
            "total_decisions": len(self._decisions),
            "decisions": [d.to_dict() for d in self._decisions],
            "summary": self._generate_summary()
        }

    def _generate_summary(self) -> dict:
        """生成摘要统计"""
        if not self._decisions:
            return {"message": "没有资产决策记录"}

        actions = {}
        sources = {}
        sections = set()

        for d in self._decisions:
            actions[d.action] = actions.get(d.action, 0) + 1
            sources[d.source] = sources.get(d.source, 0) + 1
            sections.add(d.section_id)

        return {
            "by_action": actions,
            "by_source": sources,
            "sections_covered": len(sections)
        }


# ============================================================================
# Profile 重装载工具
# ============================================================================

def reload_profile_to_state(
    profile: ProjectProfile,
    state: AgentState
) -> AgentState:
    """
    将 Profile 重装载到 AgentState

    Args:
        profile: 要装载的 Profile
        state: 目标 AgentState

    Returns:
        更新后的 AgentState
    """
    # 恢复 Manifest
    if profile.manifest:
        from .types import Manifest, SectionInfo
        state.manifest = Manifest(
            project_title=profile.manifest.get("project_title", ""),
            description=profile.manifest.get("description", ""),
            sections=[
                SectionInfo(
                    id=s["id"],
                    title=s["title"],
                    summary=s.get("summary", ""),
                    estimated_words=s.get("estimated_words", 1000),
                    metadata=s.get("metadata", {})
                )
                for s in profile.manifest.get("sections", [])
            ]
        )

    # 恢复 UAR
    if profile.uar_checkpoint:
        uar = state.initialize_uar()
        for asset_data in profile.uar_checkpoint.assets:
            from .types import AssetEntry, AssetSource, AssetQualityLevel, CropMetadata

            crop_meta = None
            if asset_data.get("crop_metadata"):
                cm = asset_data["crop_metadata"]
                crop_meta = CropMetadata(
                    left_percent=cm.get("left_percent", 0),
                    top_percent=cm.get("top_percent", 0),
                    zoom=cm.get("zoom", 1.0)
                )

            quality = None
            if asset_data.get("quality_level"):
                try:
                    quality = AssetQualityLevel(asset_data["quality_level"])
                except ValueError:
                    pass

            entry = AssetEntry(
                id=asset_data["id"],
                source=AssetSource(asset_data.get("source", "USER")),
                semantic_label=asset_data.get("semantic_label", ""),
                local_path=asset_data.get("local_path", ""),
                quality_level=quality,
                crop_metadata=crop_meta
            )
            # 直接添加到 assets 字典，不触发持久化
            uar.assets[entry.id] = entry

    # 恢复已完成章节
    if profile.completed_sections:
        state.completed_md_sections = profile.completed_sections

    print(f"[ProfileReload] 已恢复 Profile: {profile.profile_id}")
    print(f"  - Manifest: {len(profile.manifest.get('sections', [])) if profile.manifest else 0} 章节")
    print(f"  - UAR: {len(profile.uar_checkpoint.assets) if profile.uar_checkpoint else 0} 资产")
    print(f"  - 已完成章节: {len(profile.completed_sections)}")

    return state


def check_input_changes(
    profile: ProjectProfile,
    current_raw_materials: str,
    current_user_prompt: str
) -> dict:
    """
    检查输入是否有变化

    Args:
        profile: Profile
        current_raw_materials: 当前原材料内容
        current_user_prompt: 当前用户提示词

    Returns:
        变化检测结果
    """
    if not profile.input_blueprint:
        return {"changed": True, "reason": "没有输入蓝图记录"}

    bp = profile.input_blueprint
    current_raw_hash = ProfileManager._compute_hash(current_raw_materials)
    current_prompt_hash = ProfileManager._compute_hash(current_user_prompt)

    changes = []

    if current_raw_hash != bp.raw_materials_hash:
        changes.append("raw_materials")

    if current_prompt_hash != bp.user_prompt_hash:
        changes.append("user_prompt")

    return {
        "changed": len(changes) > 0,
        "changed_items": changes,
        "original_raw_hash": bp.raw_materials_hash,
        "current_raw_hash": current_raw_hash,
        "original_prompt_hash": bp.user_prompt_hash,
        "current_prompt_hash": current_prompt_hash
    }
