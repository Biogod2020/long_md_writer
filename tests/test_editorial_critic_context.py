import unittest
from unittest.mock import MagicMock, AsyncMock
from src.agents.editorial_qa_agent import EditorialQAAgent, QAIssueType
from src.core.types import AgentState
import asyncio

class TestEditorialCriticContext(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = EditorialQAAgent(client=self.mock_client)

    def test_context_audit_identifies_semantic_drift(self):
        # Setup mock VLM response for a semantic drift (terminology inconsistency)
        self.mock_client.generate_async.return_value.success = True
        self.mock_client.generate_async.return_value.text = """
        {
            "passed": false,
            "issues": [
                {
                    "type": "semantic_drift",
                    "severity": "error",
                    "location": "paragraph 2",
                    "message": "Terminology inconsistency: 'left ventricle' was used in previous chapters, but here it's called 'main pump'.",
                    "suggestion": "Use consistent terminology: 'left ventricle'."
                }
            ],
            "summary": "Full-context audit failed due to terminology drift."
        }
        """
        
        state = AgentState(job_id="test_job", workspace_path=".")
        content = "The main pump is responsible for systemic circulation."
        full_context = "# Chapter 1\nThe left ventricle is the main chamber of the heart."
        namespace = "test_ns"
        
        loop = asyncio.get_event_loop()
        new_state, report, final_content = loop.run_until_complete(
            self.agent.run_async(state, content, namespace, full_context=full_context)
        )
        
        # Verify
        self.assertFalse(report.passed)
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].issue_type, QAIssueType.SEMANTIC_DRIFT)
        
        # Verify prompt included context
        prompt_call = self.mock_client.generate_async.call_args[1]['prompt']
        # Depending on implementation, it might be a list or a string
        prompt_text = prompt_call[0]['text'] if isinstance(prompt_call, list) else prompt_call
        self.assertIn("## 全书前文上下文", prompt_text)
        self.assertIn("The left ventricle", prompt_text)

if __name__ == "__main__":
    unittest.main()
