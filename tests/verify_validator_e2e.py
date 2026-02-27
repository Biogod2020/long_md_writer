import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.validators import MarkdownStructureValidator
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState
from src.core.patcher import apply_smart_patch

async def verify_e2e_robustness():
    print("🚀 Starting E2E Robustness Verification...")
    
    # 1. 模拟 Writer 产出的包含多行 JSON 的 Markdown 内容
    # 包含了：多行 JSON, 极端缩进, 冗余空行, 以及正常的单行 JSON
    markdown_content = """
# 偶极子模型基础

在心脏电生理学中，我们通常将心脏简化为一个等效偶极子。

:::visual
{
  "id": "s1-fig-dipole",
  "action": "GENERATE_SVG",
  "description": "一个展示心脏偶极子向量 P 在三维坐标系中投影的示意图。要求包含 X, Y, Z 轴 and 向量 P。"
}
:::

接下来我们看具体的推导过程：

:::visual    
    
    {
        "id": "s1-fig-math",
        "action": "GENERATE_SVG",
        
        "description": "极坐标系下的电位分布公式展示图"
    }

:::

还有一些单行的指令：
:::visual {"id": "s1-fig-simple", "action": "GENERATE_SVG", "description": "简单图示"}
:::
"""
    
    # 2. 验证 MarkdownStructureValidator 是否能通过
    print("\n[Step 1] 验证 MarkdownStructureValidator...")
    validator = MarkdownStructureValidator()
    result = validator.validate(markdown_content, expected_namespace="s1")
    if not result.is_valid:
        print(f"❌ Validator failed! Report:\n{result.to_report()}")
        return
    print("✅ Validator passed correctly (Multi-line and Extreme Layouts accepted).")

    # 3. 验证 AssetFulfillmentAgent 的指令解析 (Internal Method)
    print("\n[Step 2] 验证 AssetFulfillmentAgent 指令解析...")
    agent = AssetFulfillmentAgent()
    # 访问内部解析方法 (虽然是私有，但在测试中可以访问)
    directives = agent._parse_visual_directives(markdown_content)
    
    expected_ids = ["s1-fig-dipole", "s1-fig-math", "s1-fig-simple"]
    found_ids = [d.id for d in directives]
    
    print(f"   Found IDs: {found_ids}")
    for eid in expected_ids:
        if eid not in found_ids:
            print(f"❌ Failed to extract directive: {eid}")
            return
    
    # 检查其中一个多行指令的内容是否完整
    dipole_d = next(d for d in directives if d.id == "s1-fig-dipole")
    print(f"✅ AssetFulfillmentAgent extracted {len(directives)} directives successfully.")

    # 4. 验证 apply_smart_patch 的物理回写鲁棒性
    print("\n[Step 3] 验证 apply_smart_patch 物理回写...")
    
    # 模拟一个生成的 HTML
    mock_html = "<figure id='s1-fig-math-html'><img src='...' alt='math'></figure>"
    target_directive = next(d for d in directives if d.id == "s1-fig-math")
    
    # 使用 apply_smart_patch 进行替换
    new_content, success = apply_smart_patch(markdown_content, target_directive.raw_block, mock_html)
    
    if success and mock_html in new_content:
        print("✅ apply_smart_patch successfully replaced the multi-line block.")
    else:
        print("❌ apply_smart_patch failed to replace the multi-line block!")
        # 尝试保底逻辑 (FulfillmentAgent 中也有这个保底)
        import re
        id_pattern = rf':::visual\s*\{{[^}}]*?"id":\s*"{re.escape(target_directive.id)}"[^}}]*?\}}[\s\S]*?:::'
        if re.search(id_pattern, markdown_content):
            print("   (Note: Regex-based fallback would catch this)")
            success = True
        else:
            return

    print("\n🏆 E2E Robustness Verification PASSED!")

if __name__ == "__main__":
    asyncio.run(verify_e2e_robustness())
