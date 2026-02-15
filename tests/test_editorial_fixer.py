import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.editorial_qa_agent import EditorialQAAgent
from src.core.types import AgentState

class TestEditorialFixer(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = EditorialQAAgent(client=self.mock_client)

    @patch("src.agents.editorial_qa_agent.run_markdown_fixer")
    @patch("src.agents.editorial_qa_agent.apply_patches")
    async def test_editorial_loop_calls_fixer(self, mock_apply, mock_run_fixer):
        # 1. Setup Critic to return an error in the first iteration
        self.mock_client.generate_async.return_value.success = True
        # First call: return error. Second call: return success.
        self.mock_client.generate_async.side_effect = [
            MagicMock(success=True, text='{"passed": false, "issues": [{"type": "crop_mismatch", "severity": "error", "location": "img", "message": "Wrong crop", "suggestion": "Fix it"}], "summary": "Error"}'),
            MagicMock(success=True, text='{"passed": true, "issues": [], "summary": "Fixed"}')
        ]
        
        # 2. Setup Fixer mock
        mock_run_fixer.return_value = {"status": "FIXED", "patches": [{"search": "old", "replace": "new"}]}
        mock_apply.return_value = "Fixed content"
        
        state = AgentState(job_id="test_job", workspace_path=".")
        content = "Original content with <img alt='test'>"
        namespace = "test_ns"
        
        # Run
        new_state, report, final_content = await self.agent.run_async(state, content, namespace)
        
        # Verify
        self.assertTrue(report.passed)
        self.assertEqual(mock_run_fixer.call_count, 1)
        self.assertEqual(mock_apply.call_count, 1)
        self.assertEqual(self.mock_client.generate_async.call_count, 2)

if __name__ == "__main__":
    unittest.main()
