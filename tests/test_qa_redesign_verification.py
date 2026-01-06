
import sys
import os
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.types import AgentState, Manifest, SectionInfo as Section
from src.agents.markdown_qa_agent import MarkdownQAAgent

# Mock Response for verification
class MockResponse:
    def __init__(self, text, success=True):
        self.text = text
        self.success = success
        self.error = None

class MockClient:
    def __init__(self):
        self.call_count = 0
        
    def generate(self, **kwargs):
        self.call_count += 1
        prompt = kwargs.get("prompt", "")
        
        # Critic Logic Mock
        if "Evaluate the content above" in prompt:
            print("[MockClient] Handling Critic Request...")
            # Simulate a "MODIFY" verdict
            return MockResponse(json.dumps({
                "verdict": "MODIFY",
                "feedback": "Section 1 needs capitalization. Section 2 is fine."
            }))
            
        # Advicer Logic Mock
        elif "Critic's General Feedback" in prompt:
             print("[MockClient] Handling Advicer Request...")
             return MockResponse(json.dumps({
                 "file1.md": "Capitalize the title."
             }))
             
        # Fixer Logic Mock
        elif "Generate SEARCH/REPLACE blocks" in prompt:
             print("[MockClient] Handling Fixer Request...")
             return MockResponse("""<<<<<<< SEARCH
# section 1
=======
# Section 1
>>>>>>>""")
             
        return MockResponse("", success=False)

def test_qa_flow():
    print("--- Starting QA Redesign Verification ---")
    
    # Setup State
    state = AgentState(
        job_id="test_job",
        workspace_path="test_workspace",
        project_brief="A test brief",
        raw_materials="Some raw materials",
        manifest=Manifest(
            project_title="Test Project",
            description="Test Description",
            sections=[Section(id="s1", title="Section 1", summary="Summary 1")]
        )
    )
    
    # Create fake files
    test_file = Path("test_workspace/md/file1.md")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("# section 1\nContent.", encoding="utf-8")
    
    state.completed_md_sections = [str(test_file)]
    state.debug_mode = True
    
    # Run Agent
    client = MockClient()
    agent = MarkdownQAAgent(client=client)
    
    new_state = agent.run(state)
    
    # Verify
    print(f"\nFinal Revision Needed: {new_state.md_qa_needs_revision}")
    
    final_content = test_file.read_text()
    print(f"Final Content:\n{final_content}")
    
    if "# Section 1" in final_content:
        print("\n✅ Verification PASSED: Content was modified.")
    else:
        print("\n❌ Verification FAILED: Content was NOT modified.")

    # Cleanup
    import shutil
    if Path("test_workspace").exists():
        shutil.rmtree("test_workspace")

if __name__ == "__main__":
    test_qa_flow()
