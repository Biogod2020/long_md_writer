
import asyncio
from pathlib import Path
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.markdown_qa_agent import MarkdownQAAgent

async def test_modify_flow():
    client = GeminiClient()
    agent = MarkdownQAAgent(client)
    
    # Setup a mock state
    workspace = Path("workspace/test_modify")
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Create sections
    s1_path = workspace / "mod-01.md"
    s1_path.write_text("# Section 1\nThis is the content of section 1. It has a typo: 'teh'.", encoding="utf-8")
    
    s2_path = workspace / "mod-02.md"
    s2_path.write_text("# Section 2\nReference file content.", encoding="utf-8")
    
    manifest = Manifest(
        project_title="Test Project",
        description="A project to test the modify flow.",
        sections=[
            SectionInfo(id="sec-1", title="Section 1", summary="Introduction"),
            SectionInfo(id="sec-2", title="Section 2", summary="Reference")
        ]
    )
    
    state = AgentState(
        job_id="test-job",
        workspace_path=str(workspace),
        manifest=manifest,
        completed_md_sections=[str(s1_path), str(s2_path)],
        debug_mode=True
    )
    
    print("\n--- Running MarkdownQAAgent.run() [Forcing MODIFY] ---")
    # We don't actually "force" it here, but the content has a typo.
    # To be SURE it modifies, we can inject a mock response or just rely on the LLM.
    # LLM usually catches typos.
    
    final_state = await agent.run(state)
    
    print("\n--- Final Status ---")
    print(f"Revision Needed: {final_state.md_qa_needs_revision}")
    print(f"Rewrite Needed: {final_state.rewrite_needed}")
    
    # Check if s1 was updated
    new_s1 = s1_path.read_text(encoding="utf-8")
    if "the" in new_s1.lower() and "teh" not in new_s1.lower():
        print("✅ SUCCESS: Section 1 was fixed!")
    else:
        print("❌ FAILURE: Section 1 was not fixed.")
        print("Content:", new_s1)

if __name__ == "__main__":
    asyncio.run(test_modify_flow())
