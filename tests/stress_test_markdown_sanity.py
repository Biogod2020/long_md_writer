import asyncio
import os
import shutil
from pathlib import Path
from src.core.types import AgentState
from src.agents.markdown_sanity_agent import MarkdownSanityAgent
from src.core.validators import MarkdownValidator
from src.core.gemini_client import GeminiClient

async def run_stress_test():
    test_ws = Path("workspace/stress_test_sanity")
    if test_ws.exists():
        shutil.rmtree(test_ws)
    test_ws.mkdir(parents=True, exist_ok=True)
    (test_ws / "md").mkdir()

    # 1. 构造测试用例
    test_files = {
        "case1_json_latex.md": """# Section 1
这里有一个带 LaTeX 转义错误的 JSON：
:::visual {
  "id": "s1-fig-1",
  "action": "GENERATE_SVG",
  "description": "心脏矢量 \\vec{P} 和 角度 \\theta"
}
:::
内容结束。
""",
        "case2_unclosed_block.md": """# Section 2
这里有一个未闭合的块：
:::important
这是重要内容，但是忘记写结尾的三个冒号了。

接下来是普通文字。
""",
        "case3_unbalanced_latex.md": """# Section 3
这里有一个不平衡的 LaTeX：
公式 $E = mc^2 没有写结尾的美元符号。
这是另一行 $x + y = z$。
"""
    }

    completed_md_sections = []
    for name, content in test_files.items():
        p = test_ws / "md" / name
        p.write_text(content, encoding="utf-8")
        completed_md_sections.append(str(p))

    # 2. 初始化状态
    state = AgentState(
        job_id="stress_test",
        workspace_path=str(test_ws),
        completed_md_sections=completed_md_sections,
        debug_mode=True
    )

    client = GeminiClient()
    agent = MarkdownSanityAgent(client=client)
    validator = MarkdownValidator()

    print("🚀 开始 Markdown Sanity 压力测试...")
    
    # 验证初始状态确实有错
    print("\n📊 初始状态校验:")
    for path in completed_md_sections:
        v = validator.validate_all(Path(path).read_text(encoding="utf-8"))
        errors = [i for i in v.issues if i.severity == "ERROR"]
        print(f"  - {Path(path).name}: Valid={v.is_valid}, Errors={len(errors)}")

    # 3. 运行 Agent
    await agent.run_async(state)

    # 4. 验证修复结果
    print("\n🏁 修复后最终校验:")
    all_passed = True
    for path in completed_md_sections:
        content = Path(path).read_text(encoding="utf-8")
        v = validator.validate_all(content)
        errors = [i for i in v.issues if i.severity == "ERROR"]
        print(f"  - {Path(path).name}: Valid={v.is_valid}, Errors={len(errors)}")
        if not v.is_valid:
            all_passed = False
            for err in errors:
                print(f"    ❌ 遗留错误: {err.message} (行 {err.line_number})")
        else:
            snippet = content[:100].replace('\n', ' ')
            print(f"    ✅ 已修复内容预览: {snippet}...")

    if all_passed:
        print("\n🎉 压力测试圆满成功！SanityAgent 成功修复了所有结构性错误。")
    else:
        print("\n⚠️ 压力测试部分失败，请检查遗留错误。")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
