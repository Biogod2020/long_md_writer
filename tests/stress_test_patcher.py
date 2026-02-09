
import asyncio
import os
import shutil
from pathlib import Path
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.markdown_qa_agent import MarkdownQAAgent
from src.core.gemini_client import GeminiClient

async def stress_test_qa_loop():
    print("🔥 [STRESS TEST] Starting Content Fixer & QA Robustness Test...")
    
    # 1. Setup mock workspace
    job_id = "stress_test_qa"
    workspace_path = Path(f"workspaces/workspace/{job_id}")
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # 2. Create a "Sick" Markdown file with intentional LaTeX and Directive errors
    md_dir = workspace_path / "md"
    md_dir.mkdir()
    target_md = md_dir / "s1-test.md"
    
    # Intentional errors:
    # - Dollar explosion risk: mixed $ and $$
    # - Directive error: unclosed :::visual
    bad_content = """# Stress Test Section

In this section, we test the potential for dollar sign explosion. 
The formula for potential is: $$$$\Phi = \frac{Q}{4\pi\epsilon r}$$$$ (This is already too many dollars!)

Also, here is a broken directive:
:::visual {"id": "v1", "action": "GENERATE_SVG", "description": "test"}
This block is never closed.

Another formula: $$ E = mc^2 $$
"""
    target_md.write_text(bad_content, encoding="utf-8")
    
    # 3. Initialize state
    state = AgentState(
        job_id=job_id,
        workspace_path=str(workspace_path),
        user_intent="Fix the formatting and ensure professional LaTeX.",
        manifest=Manifest(project_title="Stress Test", description="Test", sections=[
            SectionInfo(id="s1-test", title="Stress Test", summary="Test")
        ]),
        completed_md_sections=[str(target_md)]
    )
    
    # 4. Run MarkdownQAAgent Loop
    client = GeminiClient()
    agent = MarkdownQAAgent(client=client, max_iterations=3)
    
    print("\n🚀 [Round 1] Attempting to fix the 'Sick' file...")
    state = await agent.run(state)
    
    # Check results after Round 1
    content_after = target_md.read_text(encoding="utf-8")
    print(f"\n📄 [CONTENT AFTER R1]:\n{'-'*30}\n{content_after}\n{'-'*30}")
    
    if "$$$$" in content_after:
        print("❌ FAIL: Dollar explosion detected in R1!")
    else:
        print("✅ PASS: No dollar explosion in R1.")
        
    if ":::" in content_after and content_after.count(":::") % 2 != 0:
        print("❌ FAIL: Directive still unclosed!")
    else:
        print("✅ PASS: Directive structure balanced or handled.")

    # 5. [Round 2] Push the AI to misbehave
    # We simulate a situation where the Critic is very pedantic
    print("\n🚀 [Round 2] Forcing another audit to check for regression...")
    state.markdown_approved = False
    state.md_qa_needs_revision = True
    state = await agent.run(state)
    
    content_final = target_md.read_text(encoding="utf-8")
    print(f"\n📄 [FINAL CONTENT]:\n{'-'*30}\n{content_final}\n{'-'*30}")
    
    if "$$$$" in content_final:
        print("❌ FAIL: Dollar explosion in final state!")
    else:
        print("✅ PASS: System remained stable through multiple iterations.")

    print("\n✨ [STRESS TEST] Completed.")

if __name__ == "__main__":
    asyncio.run(stress_test_qa_loop())
