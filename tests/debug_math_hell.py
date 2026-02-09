import asyncio
import os
import shutil
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.markdown_qa_agent import MarkdownQAAgent
from src.core.gemini_client import GeminiClient

async def debug_math_hell():
    print("🧪 [DEBUG] Investigating math-hell rejection...")
    
    job_id = "debug_math_hell"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    md_dir = workspace_path / "md"
    md_dir.mkdir()
    
    fid = "math-hell"
    path = md_dir / f"{fid}.md"
    content = r"""# math-hell
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
    path.write_text(content, encoding="utf-8")

    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent="Fix all LaTeX formatting errors, ensure standard $ or $$ delimiters.",
        manifest=Manifest(project_title="Debug Math", description="Test", sections=[
            SectionInfo(id=fid, title=fid, summary="Debug")
        ]),
        completed_md_sections=[str(path)]
    )
    
    client = GeminiClient()
    agent = MarkdownQAAgent(client=client, max_iterations=1)
    
    print("\n🚀 Running single-iteration QA...")
    await agent.run(state)
    
    # Inspection
    print("\n--- Physical Files Audit ---")
    files = list(workspace_path.glob("DEBUG_REJECTED_*"))
    if files:
        for f in files:
            print(f"\n📂 FOUND REJECTED CONTENT: {f.name}")
            print("-" * 40)
            print(f.read_text())
            print("-" * 40)
    else:
        print("✅ No rejection file found.")
        print("Current file content:")
        print(path.read_text())

if __name__ == "__main__":
    asyncio.run(debug_math_hell())