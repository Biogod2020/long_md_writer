
import sys
import json
import asyncio
import shutil
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.types import AgentState, Manifest
from src.agents.markdown_qa_agent import MarkdownQAAgent
from src.agents.writer_agent import WriterAgent
from src.core.gemini_client import GeminiClient

async def run_rewrite_flow_test():
    print("\n" + "="*50)
    print("🚀 STARTING REWRITE FLOW TEST")
    print("="*50)

    workspace_id = "d2d3d333"
    orig_workspace = Path(f"workspaces/workspace/{workspace_id}")
    test_workspace = Path(f"workspaces/workspace/{workspace_id}_rewrite_flow")
    
    # 1. Setup Workspace
    if test_workspace.exists():
        shutil.rmtree(test_workspace)
    shutil.copytree(orig_workspace, test_workspace)
    
    # 2. Load State Data
    manifest = Manifest(**json.loads((test_workspace / "manifest.json").read_text()))
    log_data = json.loads((test_workspace / "debug_logs/step_001.json").read_text())
    
    # 3. Inject ENGLISH Content (Corrupt Language) into ALL sections
    print("\n💉 Injecting 'English Language' Error to trigger REWRITE...")
    md_dir = test_workspace / "md"
    completed_md = []
    for md_file in sorted(md_dir.glob("*.md")):
        new_content = f"# {md_file.stem}\n\nThis content is strictly in English, which violates the Chinese language requirement of the manifest.\n\nEverything here is English."
        md_file.write_text(new_content)
        completed_md.append(str(md_file))
        print(f"  - Overwrote {md_file.name} with English text.")

    # 4. Initialize State
    client = GeminiClient(timeout=300)
    state = AgentState(
        job_id=f"rewrite_{workspace_id}",
        workspace_path=str(test_workspace),
        raw_materials=log_data.get("raw_materials", ""),
        project_brief=log_data.get("project_brief", ""),
        manifest=manifest,
        completed_md_sections=completed_md,
        debug_mode=True
    )

    # 5. Run Markdown QA (Critic should Reject)
    qa_agent = MarkdownQAAgent(client=client)
    writer_agent = WriterAgent(client=client)

    print("\n--- [Phase 1] Running Critic (Expect REWRITE) ---")
    state = await qa_agent.run(state)
    
    if getattr(state, "rewrite_needed", False):
        print("\n✅ QA Audit Passed: REWRITE triggered.")
        print(f"Feedback: {state.rewrite_feedback[:200]}...")
    else:
        print("\n❌ QA Audit Failed: Did not trigger rewrite.")
        print(f"Verdict: {state.md_qa_needs_revision}")
        return

    # 6. Run Writer (Expect Restart)
    print("\n--- [Phase 2] Running Writer (Expect Restart) ---")
    # Writer should sense rewrite_needed, clear completed_md_sections, and write Section 1
    state = await writer_agent.run(state) # run() writes ONE section
    
    print("\n📊 Writer Verification:")
    print(f"Current Section Index: {state.current_section_index}")
    print(f"Completed Sections: {len(state.completed_md_sections)}")
    
    if len(state.completed_md_sections) == 1 and state.current_section_index == 1:
        print("✅ Writer restarted and wrote 1 section.")
    else:
        print(f"❌ Writer did not restart correctly (Sections: {len(state.completed_md_sections)})")
        return

    # 7. Check New Content Language
    new_file_path = state.completed_md_sections[0]
    new_content = Path(new_file_path).read_text()
    print(f"\n📄 New Content Preview ({Path(new_file_path).name}):")
    print(new_content[:500])
    
    # Simple heuristic check for Chinese characters
    chinese_chars = output_has_chinese(new_content)
    if chinese_chars:
        print("\n✅ New content appears to be Chinese (Rewrite Success!).")
    else:
        print("\n⚠️ New content might still be English (Check manually).")

def output_has_chinese(text):
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

if __name__ == "__main__":
    asyncio.run(run_rewrite_flow_test())
