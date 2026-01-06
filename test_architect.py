"""
独立测试 ArchitectAgent 的指令遵循和 JSON 格式正确性
"""

import sys
sys.path.insert(0, "/Users/jay/LocalProjects/long_html_writing_agent")

from src.agents.architect_agent import ArchitectAgent
from src.core.types import AgentState
from pathlib import Path
import json

# 创建临时工作目录
workspace = Path("/tmp/test_architect")
workspace.mkdir(parents=True, exist_ok=True)

# 创建初始状态
state = AgentState(
    job_id="test_architect_001",
    raw_materials="需要创建一个关于心电图导联系统的教程",
    project_brief="""
# Project Brief

## 1. Project Overview
本项目将创作《心电图物理原理》系列教程的第二章。

## 2. Target Audience
具备高中数理基础的低年级医学生。

## 3. Core Objectives
- 理解导联本质上是空间的"观测机位"
- 掌握向量点积公式

## 4. Content Scope & Depth
- 标准肢体导联 (I, II, III)
- 加压肢体导联 (aVR, aVL, aVF)
- 威尔逊中央电端 (WCT)
- 胸前导联 (V1-V6)

## 5. Pedagogical Approach
- 直觉先行，数理跟进
- 使用"手电筒与阴影"等比喻

## 6. Visual & Interactive Requirements
- 交互式向量投影演示器

## 7. Tone & Style
- 专业、严谨且富有启发性
- 中文输出
""",
    workspace_path=str(workspace),
    reference_docs=[],
    images=[],
)

def test_initial_generation():
    """测试初始 Manifest 生成"""
    print("=" * 60)
    print("测试 1: 初始 Manifest 生成")
    print("=" * 60)
    
    agent = ArchitectAgent()
    result = agent.run(state)
    
    if result.errors:
        print(f"❌ 错误: {result.errors}")
        return None
    
    if result.manifest:
        print(f"✅ 成功生成 Manifest!")
        print(f"   - 标题: {result.manifest.project_title}")
        print(f"   - 章节数: {len(result.manifest.sections)}")
        total_words = sum(s.estimated_words for s in result.manifest.sections)
        print(f"   - 总字数: {total_words}")
        for sec in result.manifest.sections:
            print(f"     - {sec.id}: {sec.title} ({sec.estimated_words} 字)")
        return result
    else:
        print("❌ 未生成 Manifest")
        return None


def test_feedback_adherence(initial_state: AgentState):
    """测试反馈遵循 - 要求减少字数"""
    print("\n" + "=" * 60)
    print("测试 2: 反馈遵循 (要求总字数控制在 10000 字以内)")
    print("=" * 60)
    
    if not initial_state or not initial_state.manifest:
        print("❌ 无初始状态，跳过测试")
        return None
    
    original_total = sum(s.estimated_words for s in initial_state.manifest.sections)
    print(f"   原始总字数: {original_total}")
    
    agent = ArchitectAgent()
    feedback = "请缩减各章节篇幅，使总字数控制在 10000 字以内。每个章节不超过 2000 字。"
    
    result = agent.run(initial_state, feedback=feedback)
    
    if result.errors:
        print(f"❌ 错误: {result.errors}")
        return None
    
    if result.manifest:
        new_total = sum(s.estimated_words for s in result.manifest.sections)
        print(f"   修改后总字数: {new_total}")
        
        if new_total <= 10000:
            print(f"✅ 成功! 字数已控制在 10000 以内")
        else:
            print(f"⚠️ 警告: 字数仍超过 10000")
        
        for sec in result.manifest.sections:
            status = "✅" if sec.estimated_words <= 2000 else "⚠️"
            print(f"     {status} {sec.id}: {sec.title} ({sec.estimated_words} 字)")
        
        return result
    else:
        print("❌ 未生成 Manifest")
        return None


def test_json_robustness():
    """测试 JSON 解析鲁棒性"""
    print("\n" + "=" * 60)
    print("测试 3: JSON 解析鲁棒性")
    print("=" * 60)
    
    agent = ArchitectAgent()
    
    # 测试常见错误格式
    test_cases = [
        # 正常 JSON
        ('{"project_title": "Test", "author": "AI", "description": "...", "sections": [{"id": "sec-1", "title": "T1", "summary": "S1", "estimated_words": 1000}], "knowledge_map": {}}', True),
        # "id": "sec-6": "title" 格式错误
        ('{"project_title": "Test", "author": "AI", "description": "...", "sections": [{"id": "sec-6": "Title", "summary": "S1", "estimated_words": 1000}], "knowledge_map": {}}', True),
    ]
    
    for i, (json_str, should_pass) in enumerate(test_cases):
        try:
            result = agent._parse_manifest(json_str)
            if should_pass:
                print(f"   ✅ 测试用例 {i+1}: 解析成功 (预期成功)")
            else:
                print(f"   ⚠️ 测试用例 {i+1}: 解析成功 (预期失败)")
        except Exception as e:
            if not should_pass:
                print(f"   ✅ 测试用例 {i+1}: 解析失败 (预期失败): {e}")
            else:
                print(f"   ❌ 测试用例 {i+1}: 解析失败 (预期成功): {e}")


if __name__ == "__main__":
    print("\n🧪 开始 ArchitectAgent 独立测试\n")
    
    # 测试 1: 初始生成
    result1 = test_initial_generation()
    
    # 测试 2: 反馈遵循
    if result1:
        test_feedback_adherence(result1)
    
    # 测试 3: JSON 鲁棒性
    test_json_robustness()
    
    print("\n🏁 测试完成\n")
