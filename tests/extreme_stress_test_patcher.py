import asyncio
import os
import shutil
import random
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.markdown_qa_agent import MarkdownQAAgent
from src.core.gemini_client import GeminiClient

async def create_hell_content(file_id):
    """生成包含复杂错误的极端测试内容"""
    if file_id == "math-hell":
        return r"""# math-hell
Deeply nested math test:
1. Fraction error: $$$$ \frac{1}{\frac{q}{\pi \epsilon r}} $$$$
2. Mixed delimiters: $\Phi$ vs $$$$\Psi$$$$ vs $$\Omega$
3. Illegal triple sign: $$$ \alpha + \beta $$$
4. Matrix trap:
$$
\begin{pmatrix}
a & b \\
c & d
\end{pmatrix}
$$
Wait, here is a dollar sign in the middle of a word: bu$$iness.
"""
    elif file_id == "long-form":
        lorem = "The heart vector represents the sum of all electrical activity. " * 1000
        return rf"# {file_id}\n{lorem}\n\nERROR_HERE: $$$$\vec{{H}} = \sum \vec{{p}}_i$$$$"
    elif file_id == "directive-chaos":
        return r"""# directive-chaos
:::visual {"id": "v1", "action": "GENERATE_SVG"}
Nested important block:
:::important
This should not be allowed to remain unclosed inside a visual.
:::
This visual is missing its closing tag too.
"""
    else:
        return f"# {file_id}\nNormal content with one error: $$$$E=mc^2$$$$"

async def extreme_stress_test():
    print("🚀 [EXTREME STRESS TEST] Initiating High-Intensity QA Audit...")
    
    job_id = "extreme_stress_qa"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate 10 high-complexity files
    md_dir = workspace_path / "md"
    md_dir.mkdir()
    
    file_ids = ["math-hell", "long-form", "directive-chaos"] + [f"extra-{i}" for i in range(7)]
    completed_sections = []
    sections_info = []
    
    for fid in file_ids:
        path = md_dir / f"{fid}.md"
        content = await create_hell_content(fid)
        path.write_text(content, encoding="utf-8")
        completed_sections.append(str(path))
        sections_info.append(SectionInfo(id=fid, title=fid, summary="Stress test"))

    # 2. Setup State
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent="Fix all LaTeX formatting errors, ensure standard $ or $$ delimiters, close all blocks, and optimize professional tone.",
        manifest=Manifest(project_title="Hell Project", description="Extreme Stress Test", sections=sections_info),
        completed_md_sections=completed_sections,
        reference_materials="Global physical constants: epsilon_0 = 8.85e-12. All heart vectors are represented by H."
    )
    
    # 3. Execution
    client = GeminiClient()
    agent = MarkdownQAAgent(client=client, max_iterations=3)
    
    print(f"\n🔥 [HELL ROUND] Processing {len(file_ids)} problematic files in parallel...")
    state = await agent.run(state)
    
    # 4. Result Audit
    print("\n🔬 [AUDIT PHASE] Checking for regressions and explosions...")
    
    overall_pass = True
    for fid in file_ids:
        path = md_dir / f"{fid}.md"
        text = path.read_text(encoding="utf-8")
        
        # Check 1: Dollar explosion
        if "$$$" in text:
            print(f"❌ REGRESSION in {fid}: Triple/Quadruple dollars found!")
            overall_pass = False
        
        # Check 2: Directives
        if text.count(":::") % 2 != 0:
            print(f"❌ STRUCTURAL ERROR in {fid}: Unbalanced ::: containers!")
            overall_pass = False
            
        # Check 3: Logic (Simplified)
        if fid == "math-hell" and "\\frac" in text and "$$$$" in text:
             print(f"❌ REPAIR FAILED in {fid}: Matrix/Fraction math remains broken.")
             overall_pass = False

    if overall_pass:
        print("\n🏆 [RESULT] SYSTEM STOOD THE PRESSURE! All '毒补丁' were blocked or neutralized.")
    else:
        print("\n💀 [RESULT] SYSTEM COMPROMISED. Issues detected in extreme conditions.")

    # Show a snippet of the hardest file
    math_hell_final = (md_dir / "math-hell.md").read_text()
    print(f"\n📄 [MATH-HELL SNIPPET]:\n{'-'*30}\n{math_hell_final[:500]}\n{'-'*30}")

if __name__ == "__main__":
    asyncio.run(extreme_stress_test())