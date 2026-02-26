import unittest
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.editorial_qa_agent import EditorialQAAgent
from src.core.types import AgentState, Manifest, SectionInfo
from pathlib import Path
import shutil
import json
import tempfile

class TestEditorialQuotaStress(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.mock_client = MagicMock()
        self.agent = EditorialQAAgent(client=self.mock_client, max_iterations=5)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("src.agents.editorial_qa_agent.run_editorial_critic")
    @patch("src.agents.editorial_qa_agent.run_editorial_advicer")
    @patch("src.agents.editorial_qa_agent.run_markdown_fixer")
    @patch("src.agents.editorial_qa_agent.merge_markdown_sections")
    async def test_phase1_structural_defense(self, mock_merge, mock_run_fixer, mock_advicer, mock_critic):
        """
        Verify that Phase 1 (Mechanical Defense) correctly intercepts and fixes 
        structural issues before the AI Critic is even called.
        """
        # 1. Setup file with a structural error (unclosed block)
        md_content = "# Header\n:::visual {\"id\": \"s1-fig-1\"}\nUnclosed block!\n"
        merged_path = self.test_dir / "final_full.md"
        merged_path.write_text(md_content, encoding="utf-8")
        
        # 2. Setup Mocks
        mock_merge.return_value = True
        # Mock fixer to fix the block
        mock_run_fixer.return_value = {"status": "FIXED", "patches": [{"search": "!", "replace": "!\n:::"}]}
        
        # Mock Critic to Approve AFTER the fix (using side_effect to allow first check)
        mock_critic.return_value = {"verdict": "APPROVE", "feedback": "Looks good now"}
        
        # 3. Setup State
        state = AgentState(
            job_id="stress_test", 
            workspace_path=str(self.test_dir),
            completed_md_sections=[str(self.test_dir / "sec1.md")]
        )
        state.manifest = Manifest(project_title="Test", description="test", sections=[SectionInfo(id="s1", title="Sec 1", summary="test")])

        # Execute
        await self.agent.run_async(state)

        # 5. Verify logic
        # run_markdown_fixer should be called by Phase 1
        self.assertTrue(mock_run_fixer.called)
        # critic should be called AFTER phase 1 fix
        self.assertTrue(mock_critic.called)

    @patch("src.agents.editorial_qa_agent.run_editorial_critic")
    @patch("src.agents.editorial_qa_agent.run_editorial_advicer")
    @patch("src.agents.editorial_qa_agent.run_markdown_fixer")
    @patch("src.agents.editorial_qa_agent.merge_markdown_sections")
    async def test_rollback_mechanism(self, mock_merge, mock_run_fixer, mock_advicer, mock_critic):
        """
        Verify that if a patch from the Advicer breaks the structure, 
        it is rolled back.
        """
        # 1. Valid file
        md_content = "# Header\nValid content.\n"
        merged_path = self.test_dir / "final_full.md"
        merged_path.write_text(md_content, encoding="utf-8")
        
        # 2. Mocks
        mock_merge.return_value = True
        # Critic says MODIFY
        mock_critic.return_value = {"verdict": "MODIFY", "feedback": "Fix logic"}
        # Advicer gives a plan
        mock_advicer.return_value = {"final_full.md": "Step 1: Break it"}
        
        # Fixer returns a patch that introduces an unclosed block
        broken_patch = "# Header\n:::visual {\"id\": \"s1-broken\"}\nNo closure!\n"
        mock_run_fixer.return_value = {"status": "FIXED", "patches": [{"search": "Valid content.", "replace": broken_patch}]}
        
        state = AgentState(
            job_id="rollback_test", 
            workspace_path=str(self.test_dir),
            completed_md_sections=[str(self.test_dir / "sec1.md")]
        )
        state.manifest = Manifest(project_title="Test", description="test", sections=[SectionInfo(id="s1", title="Sec 1", summary="test")])

        # 3. Run
        self.agent.max_iterations = 2
        await self.agent.run_async(state)

        # 4. Verify Rollback
        # The file content should still be the ORIGINAL because the patch was broken
        final_content = merged_path.read_text(encoding="utf-8")
        self.assertEqual(final_content, md_content)
        self.assertNotIn("broken", final_content)

if __name__ == "__main__":
    unittest.main()
