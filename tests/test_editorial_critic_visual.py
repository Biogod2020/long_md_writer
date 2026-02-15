import unittest
from unittest.mock import MagicMock, AsyncMock
from src.agents.editorial_qa_agent import EditorialQAAgent, QAIssueType
from src.core.types import AgentState
from tests.resources.mock_renderer import MockRenderer
from pathlib import Path
import shutil
import asyncio

class TestEditorialCriticVisual(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        # Mocking async generate method
        self.mock_client.generate_async = AsyncMock()
        
        self.test_dir = Path("test_output/critic_visual")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.renderer = MockRenderer(self.test_dir)
        
        self.agent = EditorialQAAgent(client=self.mock_client)
        # Inject mock renderer (we'll need to modify the Agent to accept this)
        self.agent.renderer = self.renderer

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_visual_audit_identifies_crop_mismatch(self):
        # Setup mock VLM response for a crop mismatch
        self.mock_client.generate_async.return_value.success = True
        self.mock_client.generate_async.return_value.text = """
        {
            "passed": false,
            "issues": [
                {
                    "type": "crop_mismatch",
                    "severity": "error",
                    "location": "img_01",
                    "message": "The focus of the image (the heart valve) is cut off.",
                    "suggestion": "Adjust object-position to center."
                }
            ],
            "summary": "Visual audit failed."
        }
        """
        
        state = AgentState(
            job_id="test_job",
            workspace_path=str(self.test_dir)
        )
        content = "Markdown content with <img id='img_01' src='assets/test.jpg' alt='test image'>"
        full_context = "# Chapter 0\nPrevious context."
        namespace = "test_ns"
        
        # Run the agent
        loop = asyncio.get_event_loop()
        new_state, report, final_content = loop.run_until_complete(
            self.agent.run_async(state, content, namespace, full_context=full_context)
        )
        
        # Verify
        self.assertFalse(report.passed)
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].issue_type, QAIssueType.CROP_MISMATCH)
        
        # Verify renderer was used (indirectly, by checking if image exists)
        # Note: In a real test, we'd mock the renderer call or check side effects
        
if __name__ == "__main__":
    unittest.main()
