import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.editorial_qa_agent import EditorialQAAgent
from src.core.types import AgentState
from tests.resources.mock_renderer import MockRenderer
from pathlib import Path
import shutil

class TestEditorialE2E(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        
        self.test_dir = Path("test_output/e2e_editorial")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.renderer = MockRenderer(self.test_dir)
        
        self.agent = EditorialQAAgent(client=self.mock_client, renderer=self.renderer)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("src.agents.editorial_qa_agent.run_markdown_fixer")
    @patch("src.agents.editorial_qa_agent.apply_patches")
    async def test_e2e_visual_and_context_fix(self, mock_apply, mock_run_fixer):
        # 1. Setup Critic responses
        # Iteration 1: Returns two errors (one visual, one context)
        # Iteration 2: Returns success
        self.mock_client.generate_async.side_effect = [
            MagicMock(success=True, text='''
            {
                "passed": false,
                "issues": [
                    {"type": "crop_mismatch", "severity": "error", "location": "img_01", "message": "Broken crop", "suggestion": "Center it"},
                    {"type": "semantic_drift", "severity": "error", "location": "text", "message": "Wrong term", "suggestion": "Use 'Ventricle'"}
                ],
                "summary": "Multiple issues"
            }
            '''),
            MagicMock(success=True, text='{"passed": true, "issues": [], "summary": "All fixed"}')
        ]
        
        # 2. Setup Fixer responses
        mock_run_fixer.side_effect = [
            {"status": "FIXED", "patches": [{"search": "old1", "replace": "new1"}]}, # Fix 1
            {"status": "FIXED", "patches": [{"search": "old2", "replace": "new2"}]}  # Fix 2
        ]
        
        # mock_apply returns updated content each time
        mock_apply.side_effect = [
            "Content with fix 1",
            "Content with fix 1 and 2"
        ]
        
        state = AgentState(job_id="test_job", workspace_path=str(self.test_dir))
        content = "Original content with <img id='img_01' src='test.jpg' alt='test'>"
        full_context = "# Context\nTerminology: Ventricle"
        namespace = "e2e_ns"
        
        # Run
        new_state, report = await self.agent.run_async(state, content, namespace, full_context=full_context)
        
        # Verify
        self.assertTrue(report.passed)
        self.assertEqual(mock_run_fixer.call_count, 2)
        self.assertEqual(mock_apply.call_count, 2)
        self.assertEqual(self.mock_client.generate_async.call_count, 2)
        
        # Verify screenshots were generated for each iteration
        self.assertTrue((self.test_dir / "qa_e2e_ns_1.png").exists())
        self.assertTrue((self.test_dir / "qa_e2e_ns_2.png").exists())

if __name__ == "__main__":
    unittest.main()
