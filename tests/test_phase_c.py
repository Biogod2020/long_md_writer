"""
Phase C 集成测试: 实验管理与 Profile 持久化

测试内容：
1. ProfileManager - Profile 创建、保存、加载、删除
2. ProjectProfile - 快照记录和序列化
3. AssetService - 资产决策链追踪
4. Profile 重装载 - 状态恢复
"""

import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.types import (
    AgentState,
    Manifest,
    SectionInfo,
    AssetEntry,
    AssetSource,
    AssetQualityLevel,
    CropMetadata
)
from src.core.persistence import (
    ProfileManager,
    ProjectProfile,
    ProfileStatus,
    PromptSnapshot,
    InputBlueprint,
    UARCheckpoint,
    AssetDecision,
    AssetService,
    reload_profile_to_state,
    check_input_changes
)


# ============================================================================
# 测试夹具
# ============================================================================

def create_test_state() -> AgentState:
    """创建测试用的 AgentState"""
    state = AgentState(
        job_id="test-job",
        workspace_path="/tmp/test",
        raw_materials="这是测试原材料内容...",
        project_brief="测试项目简介"
    )

    # 初始化 UAR 并添加一些资产
    uar = state.initialize_uar()
    uar.register_immediate(AssetEntry(
        id="s1-fig-test",
        source=AssetSource.USER,
        semantic_label="测试图片",
        local_path="/assets/test.png",
        quality_level=AssetQualityLevel.HIGH
    ))
    uar.register_immediate(AssetEntry(
        id="s1-fig-generated",
        source=AssetSource.AI,
        semantic_label="生成的 SVG",
        local_path="/generated/test.svg",
        quality_level=AssetQualityLevel.MEDIUM,
        crop_metadata=CropMetadata(left_percent=10, top_percent=20, zoom=1.5)
    ))

    # 设置 Manifest
    state.manifest = Manifest(
        project_title="测试项目",
        description="这是一个测试项目",
        sections=[
            SectionInfo(
                id="sec-1",
                title="第一章",
                summary="第一章摘要",
                estimated_words=1000
            ),
            SectionInfo(
                id="sec-2",
                title="第二章",
                summary="第二章摘要",
                estimated_words=1500
            )
        ]
    )

    return state


# ============================================================================
# 测试 1: ProfileManager 基本操作
# ============================================================================

def test_profile_manager_create():
    """测试 Profile 创建"""
    print("\n" + "=" * 60)
    print("测试 1: ProfileManager 创建")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))

        # 创建 Profile
        profile = manager.create_profile(
            project_title="测试项目",
            profile_id="test-profile-001",
            tags=["测试", "实验"]
        )

        print(f"\n创建的 Profile:")
        print(f"  ID: {profile.profile_id}")
        print(f"  标题: {profile.project_title}")
        print(f"  状态: {profile.status.value}")
        print(f"  标签: {profile.tags}")

        assert profile.profile_id == "test-profile-001"
        assert profile.project_title == "测试项目"
        assert profile.status == ProfileStatus.ACTIVE
        assert "测试" in profile.tags

        # 验证文件已创建
        profile_path = Path(tmpdir) / "test-profile-001" / "profile.json"
        assert profile_path.exists(), "Profile 文件应该已创建"

        print("\n✓ Profile 创建测试通过")


def test_profile_manager_save_load():
    """测试 Profile 保存和加载"""
    print("\n" + "=" * 60)
    print("测试 2: ProfileManager 保存和加载")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))

        # 创建并配置 Profile
        profile = manager.create_profile(
            project_title="保存加载测试",
            profile_id="save-load-test"
        )

        # 添加提示词快照
        manager.record_prompt(
            agent_name="WriterAgent",
            system_instruction="你是一位专业作家...",
            user_prompt_template="请创作关于 {topic} 的内容",
            parameters={"temperature": 0.7}
        )

        # 添加输入蓝图
        manager.record_input_blueprint(
            raw_materials_path="/inputs/raw.md",
            raw_materials_content="原材料内容...",
            user_prompt_path="/inputs/prompt.txt",
            user_prompt_content="用户指令...",
            assets_dir="/assets",
            asset_files=["img1.png", "img2.svg"]
        )

        # 保存
        assert manager.save_profile(), "保存应该成功"

        # 创建新的 manager 并加载
        manager2 = ProfileManager(profiles_dir=Path(tmpdir))
        loaded = manager2.load_profile("save-load-test")

        print(f"\n加载的 Profile:")
        print(f"  ID: {loaded.profile_id}")
        print(f"  提示词数量: {len(loaded.prompts)}")
        print(f"  输入蓝图: {'有' if loaded.input_blueprint else '无'}")

        assert loaded is not None
        assert loaded.profile_id == "save-load-test"
        assert len(loaded.prompts) == 1
        assert loaded.prompts[0].agent_name == "WriterAgent"
        assert loaded.input_blueprint is not None
        assert loaded.input_blueprint.raw_materials_path == "/inputs/raw.md"

        print("\n✓ Profile 保存加载测试通过")


def test_profile_manager_list():
    """测试 Profile 列表"""
    print("\n" + "=" * 60)
    print("测试 3: ProfileManager 列表")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))

        # 创建多个 Profile
        manager.create_profile("项目 A", "profile-a", ["tag1"])
        manager.create_profile("项目 B", "profile-b", ["tag2"])
        manager.create_profile("项目 C", "profile-c", ["tag1", "tag3"])

        # 列出所有 Profile
        profiles = manager.list_profiles()

        print(f"\nProfile 列表 ({len(profiles)} 个):")
        for p in profiles:
            print(f"  - {p['profile_id']}: {p['project_title']} ({p['status']})")

        assert len(profiles) == 3
        profile_ids = [p["profile_id"] for p in profiles]
        assert "profile-a" in profile_ids
        assert "profile-b" in profile_ids
        assert "profile-c" in profile_ids

        print("\n✓ Profile 列表测试通过")


def test_profile_manager_delete():
    """测试 Profile 删除"""
    print("\n" + "=" * 60)
    print("测试 4: ProfileManager 删除")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))

        # 创建 Profile
        manager.create_profile("待删除项目", "to-delete")

        # 验证存在
        profiles = manager.list_profiles()
        assert len(profiles) == 1

        # 删除
        result = manager.delete_profile("to-delete")
        print(f"\n删除结果: {result}")

        # 验证已删除
        profiles = manager.list_profiles()
        assert len(profiles) == 0

        # 再次删除应该返回 False
        result = manager.delete_profile("to-delete")
        assert not result

        print("\n✓ Profile 删除测试通过")


def test_profile_manager_archive():
    """测试 Profile 归档"""
    print("\n" + "=" * 60)
    print("测试 5: ProfileManager 归档")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))

        # 创建 Profile
        manager.create_profile("待归档项目", "to-archive")

        # 归档
        result = manager.archive_profile("to-archive")
        print(f"\n归档结果: {result}")

        # 验证状态
        loaded = manager.load_profile("to-archive")
        assert loaded.status == ProfileStatus.ARCHIVED

        print(f"归档后状态: {loaded.status.value}")

        print("\n✓ Profile 归档测试通过")


# ============================================================================
# 测试 2: ProjectProfile 快照记录
# ============================================================================

def test_profile_record_uar():
    """测试 UAR 检查点记录"""
    print("\n" + "=" * 60)
    print("测试 6: UAR 检查点记录")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))
        manager.create_profile("UAR 测试", "uar-test")

        # 创建带有资产的 State
        state = create_test_state()

        # 记录 UAR 检查点
        manager.record_uar_checkpoint(state)
        manager.save_profile()

        # 验证
        profile = manager.current_profile
        assert profile.uar_checkpoint is not None
        print(f"\n记录的资产数量: {len(profile.uar_checkpoint.assets)}")

        for asset in profile.uar_checkpoint.assets:
            print(f"  - {asset['id']}: {asset['semantic_label']} ({asset['source']})")

        assert len(profile.uar_checkpoint.assets) == 2

        print("\n✓ UAR 检查点记录测试通过")


def test_profile_record_manifest():
    """测试 Manifest 记录"""
    print("\n" + "=" * 60)
    print("测试 7: Manifest 记录")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))
        manager.create_profile("Manifest 测试", "manifest-test")

        # 创建 Manifest
        manifest = Manifest(
            project_title="心电图教程",
            description="详细的心电图物理原理教程",
            sections=[
                SectionInfo(id="sec-1", title="导联概念", summary="介绍导联", estimated_words=2000),
                SectionInfo(id="sec-2", title="波形分析", summary="分析波形", estimated_words=2500)
            ]
        )

        # 记录
        manager.record_manifest(manifest)
        manager.save_profile()

        # 验证
        profile = manager.current_profile
        assert profile.manifest is not None
        print(f"\n记录的 Manifest:")
        print(f"  标题: {profile.manifest['project_title']}")
        print(f"  章节数: {len(profile.manifest['sections'])}")

        for sec in profile.manifest["sections"]:
            print(f"    - {sec['id']}: {sec['title']}")

        assert profile.manifest["project_title"] == "心电图教程"
        assert len(profile.manifest["sections"]) == 2

        print("\n✓ Manifest 记录测试通过")


def test_profile_record_sections():
    """测试已完成章节记录"""
    print("\n" + "=" * 60)
    print("测试 8: 已完成章节记录")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))
        manager.create_profile("章节测试", "sections-test")

        # 记录章节
        manager.record_completed_section("sec-1", "# 第一章内容\n\n这是第一章...")
        manager.record_completed_section("sec-2", "# 第二章内容\n\n这是第二章...")
        manager.save_profile()

        # 验证
        profile = manager.current_profile
        print(f"\n记录的章节数: {len(profile.completed_sections)}")

        for sec_id, content in profile.completed_sections.items():
            print(f"  - {sec_id}: {len(content)} 字符")

        assert len(profile.completed_sections) == 2
        assert "sec-1" in profile.completed_sections
        assert "第一章" in profile.completed_sections["sec-1"]

        print("\n✓ 已完成章节记录测试通过")


def test_profile_status_transitions():
    """测试 Profile 状态转换"""
    print("\n" + "=" * 60)
    print("测试 9: Profile 状态转换")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))
        profile = manager.create_profile("状态测试", "status-test")

        print(f"\n初始状态: {profile.status.value}")
        assert profile.status == ProfileStatus.ACTIVE

        # 标记完成
        manager.mark_completed()
        profile = manager.current_profile
        print(f"完成后状态: {profile.status.value}")
        assert profile.status == ProfileStatus.COMPLETED

        # 创建新 Profile 并标记失败
        manager.create_profile("失败测试", "fail-test")
        manager.mark_failed("测试错误信息")
        profile = manager.current_profile
        print(f"失败后状态: {profile.status.value}")
        print(f"失败备注: {profile.notes}")
        assert profile.status == ProfileStatus.FAILED
        assert "测试错误" in profile.notes

        print("\n✓ Profile 状态转换测试通过")


# ============================================================================
# 测试 3: AssetService 资产决策链
# ============================================================================

def test_asset_service_decisions():
    """测试资产决策记录"""
    print("\n" + "=" * 60)
    print("测试 10: AssetService 决策记录")
    print("=" * 60)

    service = AssetService()

    # 记录决策
    service.record_decision(
        asset_id="s1-fig-test",
        action="USE_EXISTING",
        source="USER",
        driving_intent="需要一张展示电极位置的图",
        section_id="sec-1",
        context="用户提供的素材中已有合适图片"
    )

    service.record_decision(
        asset_id="s1-fig-generated",
        action="GENERATE_SVG",
        source="AI",
        driving_intent="需要爱因托芬三角形示意图",
        section_id="sec-1",
        context="UAR 中无匹配资产，使用 LLM 生成"
    )

    service.record_decision(
        asset_id="s2-fig-wave",
        action="SEARCH_WEB",
        source="WEB",
        driving_intent="需要真实的心电波形图",
        section_id="sec-2",
        context="需要临床真实案例"
    )

    # 获取所有决策
    decisions = service.get_decision_chain()
    print(f"\n记录的决策数: {len(decisions)}")

    for d in decisions:
        print(f"  - {d['asset_id']}: {d['action']} ({d['source']})")
        print(f"    意图: {d['driving_intent']}")

    assert len(decisions) == 3

    print("\n✓ 资产决策记录测试通过")


def test_asset_service_filter():
    """测试资产决策过滤"""
    print("\n" + "=" * 60)
    print("测试 11: AssetService 决策过滤")
    print("=" * 60)

    service = AssetService()

    # 记录多个决策
    service.record_decision("a1", "USE_EXISTING", "USER", "意图1", "sec-1", "")
    service.record_decision("a2", "GENERATE_SVG", "AI", "意图2", "sec-1", "")
    service.record_decision("a3", "SEARCH_WEB", "WEB", "意图3", "sec-2", "")
    service.record_decision("a4", "GENERATE_SVG", "AI", "意图4", "sec-2", "")

    # 按资产 ID 过滤
    a1_decisions = service.get_decision_chain("a1")
    print(f"\n资产 a1 的决策数: {len(a1_decisions)}")
    assert len(a1_decisions) == 1

    # 按章节过滤
    sec1_assets = service.get_section_assets("sec-1")
    sec2_assets = service.get_section_assets("sec-2")
    print(f"sec-1 的资产数: {len(sec1_assets)}")
    print(f"sec-2 的资产数: {len(sec2_assets)}")
    assert len(sec1_assets) == 2
    assert len(sec2_assets) == 2

    print("\n✓ 资产决策过滤测试通过")


def test_asset_service_dashboard():
    """测试资产看板"""
    print("\n" + "=" * 60)
    print("测试 12: AssetService 看板")
    print("=" * 60)

    state = create_test_state()
    service = AssetService()

    # 获取看板数据
    dashboard = service.get_asset_dashboard(state)

    print(f"\n资产看板:")
    print(f"  总资产数: {dashboard['total']}")
    print(f"  按来源分布: {dashboard['by_source']}")
    print(f"  按质量分布: {dashboard['by_quality']}")
    print(f"  复用率: {dashboard['reuse_rate']}")

    assert dashboard["total"] == 2
    assert dashboard["by_source"]["USER"] == 1
    assert dashboard["by_source"]["AI"] == 1
    assert dashboard["reuse_rate"] == 0.5

    print("\n✓ 资产看板测试通过")


def test_asset_service_report():
    """测试资产报告导出"""
    print("\n" + "=" * 60)
    print("测试 13: AssetService 报告导出")
    print("=" * 60)

    service = AssetService()

    # 记录决策
    service.record_decision("a1", "USE_EXISTING", "USER", "意图1", "sec-1", "")
    service.record_decision("a2", "GENERATE_SVG", "AI", "意图2", "sec-1", "")
    service.record_decision("a3", "GENERATE_SVG", "AI", "意图3", "sec-2", "")

    # 导出报告
    report = service.export_report()

    print(f"\n报告内容:")
    print(f"  生成时间: {report['generated_at']}")
    print(f"  总决策数: {report['total_decisions']}")
    print(f"  摘要: {json.dumps(report['summary'], ensure_ascii=False, indent=4)}")

    assert report["total_decisions"] == 3
    assert report["summary"]["by_action"]["GENERATE_SVG"] == 2
    assert report["summary"]["by_action"]["USE_EXISTING"] == 1
    assert report["summary"]["sections_covered"] == 2

    print("\n✓ 资产报告导出测试通过")


# ============================================================================
# 测试 4: Profile 重装载
# ============================================================================

def test_profile_reload():
    """测试 Profile 重装载到 State"""
    print("\n" + "=" * 60)
    print("测试 14: Profile 重装载")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))

        # 创建并保存完整的 Profile
        manager.create_profile("重装载测试", "reload-test")

        # 使用已有的 state 记录快照
        original_state = create_test_state()
        manager.record_uar_checkpoint(original_state)
        manager.record_manifest(original_state.manifest)
        manager.record_completed_section("sec-1", "# 第一章\n\n内容...")
        manager.save_profile()

        # 创建新的空 State
        new_state = AgentState(
            job_id="new-job",
            workspace_path="/tmp/new",
            raw_materials="",
            project_brief=""
        )

        # 重装载
        loaded_profile = manager.load_profile("reload-test")
        restored_state = reload_profile_to_state(loaded_profile, new_state)

        # 验证恢复
        print(f"\n恢复后的状态:")
        print(f"  Manifest 标题: {restored_state.manifest.project_title if restored_state.manifest else 'None'}")
        print(f"  Manifest 章节数: {len(restored_state.manifest.sections) if restored_state.manifest else 0}")

        uar = restored_state.get_uar()
        print(f"  UAR 资产数: {len(uar.assets) if uar else 0}")

        completed = restored_state.completed_md_sections
        print(f"  已完成章节: {list(completed.keys()) if completed else []}")

        assert restored_state.manifest is not None
        assert restored_state.manifest.project_title == "测试项目"
        assert len(restored_state.manifest.sections) == 2
        assert uar is not None
        assert len(uar.assets) == 2
        assert "sec-1" in completed

        print("\n✓ Profile 重装载测试通过")


def test_input_change_detection():
    """测试输入变化检测"""
    print("\n" + "=" * 60)
    print("测试 15: 输入变化检测")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))
        manager.create_profile("变化检测测试", "change-test")

        # 记录原始输入
        original_raw = "原始材料内容 v1"
        original_prompt = "原始指令 v1"

        manager.record_input_blueprint(
            raw_materials_path="/inputs/raw.md",
            raw_materials_content=original_raw,
            user_prompt_path="/inputs/prompt.txt",
            user_prompt_content=original_prompt,
            assets_dir="/assets"
        )
        manager.save_profile()

        profile = manager.current_profile

        # 测试无变化
        result = check_input_changes(profile, original_raw, original_prompt)
        print(f"\n无变化检测: {result}")
        assert not result["changed"]

        # 测试原材料变化
        result = check_input_changes(profile, "修改后的材料", original_prompt)
        print(f"原材料变化检测: {result}")
        assert result["changed"]
        assert "raw_materials" in result["changed_items"]

        # 测试指令变化
        result = check_input_changes(profile, original_raw, "修改后的指令")
        print(f"指令变化检测: {result}")
        assert result["changed"]
        assert "user_prompt" in result["changed_items"]

        # 测试两者都变化
        result = check_input_changes(profile, "新材料", "新指令")
        print(f"全部变化检测: {result}")
        assert result["changed"]
        assert len(result["changed_items"]) == 2

        print("\n✓ 输入变化检测测试通过")


# ============================================================================
# 测试 5: 序列化与反序列化
# ============================================================================

def test_full_serialization():
    """测试完整的序列化和反序列化"""
    print("\n" + "=" * 60)
    print("测试 16: 完整序列化")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ProfileManager(profiles_dir=Path(tmpdir))
        manager.create_profile("序列化测试", "serial-test", tags=["test", "serialization"])

        # 记录所有类型的数据
        manager.record_prompt("Agent1", "系统指令1", "模板1", {"p1": "v1"})
        manager.record_prompt("Agent2", "系统指令2", "模板2", {"p2": "v2"})

        manager.record_input_blueprint(
            "/raw.md", "raw content",
            "/prompt.txt", "prompt content",
            "/assets",
            ["a.png", "b.svg"],
            {"mode": "test"}
        )

        state = create_test_state()
        manager.record_uar_checkpoint(state)
        manager.record_manifest(state.manifest)
        manager.record_completed_section("sec-1", "内容1")
        manager.record_completed_section("sec-2", "内容2")

        manager.save_profile()

        # 验证文件
        profile_dir = Path(tmpdir) / "serial-test"
        print(f"\n生成的文件:")
        for f in profile_dir.iterdir():
            print(f"  - {f.name}: {f.stat().st_size} bytes")

        assert (profile_dir / "profile.json").exists()
        assert (profile_dir / "prompts_snapshot.json").exists()
        assert (profile_dir / "input_blueprint.json").exists()
        assert (profile_dir / "uar_checkpoint.json").exists()

        # 完全重新加载并验证
        manager2 = ProfileManager(profiles_dir=Path(tmpdir))
        loaded = manager2.load_profile("serial-test")

        assert loaded.profile_id == "serial-test"
        assert len(loaded.prompts) == 2
        assert loaded.input_blueprint is not None
        assert loaded.uar_checkpoint is not None
        assert len(loaded.uar_checkpoint.assets) == 2
        assert loaded.manifest is not None
        assert len(loaded.completed_sections) == 2

        print("\n✓ 完整序列化测试通过")


# ============================================================================
# 主函数
# ============================================================================

def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("Phase C 集成测试: 实验管理与 Profile 持久化")
    print("=" * 70)

    # ProfileManager 基本操作
    print("\n" + "#" * 70)
    print("# ProfileManager 基本操作测试")
    print("#" * 70)

    test_profile_manager_create()
    test_profile_manager_save_load()
    test_profile_manager_list()
    test_profile_manager_delete()
    test_profile_manager_archive()

    # 快照记录测试
    print("\n" + "#" * 70)
    print("# 快照记录测试")
    print("#" * 70)

    test_profile_record_uar()
    test_profile_record_manifest()
    test_profile_record_sections()
    test_profile_status_transitions()

    # AssetService 测试
    print("\n" + "#" * 70)
    print("# AssetService 资产决策链测试")
    print("#" * 70)

    test_asset_service_decisions()
    test_asset_service_filter()
    test_asset_service_dashboard()
    test_asset_service_report()

    # Profile 重装载测试
    print("\n" + "#" * 70)
    print("# Profile 重装载测试")
    print("#" * 70)

    test_profile_reload()
    test_input_change_detection()

    # 序列化测试
    print("\n" + "#" * 70)
    print("# 序列化测试")
    print("#" * 70)

    test_full_serialization()

    # 总结
    print("\n" + "=" * 70)
    print("所有 Phase C 测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
