import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock
from src.agents.editorial_qa_agent import EditorialQAAgent, QAIssue, QAIssueType, QASeverity
from src.core.types import AgentState
from src.core.gemini_client import GeminiClient

class TestBackoffIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_editorial_qa_backoff_injection(self):
        # Setup
        mock_client = MagicMock(spec=GeminiClient)
        agent = EditorialQAAgent(client=mock_client)
        
        state = AgentState(
            user_context="test",
            workspace_path="workspace_test",
            job_id="test_job"
        )
        
        content = "Initial content"
        namespace = "s1"
        
        # Mock _run_local_checks to return an error
        agent._run_local_checks = MagicMock(return_value=[
            QAIssue(
                issue_type=QAIssueType.BROKEN_REFERENCE,
                severity=QASeverity.ERROR,
                location="everywhere",
                message="Broken ref",
                suggestion="Fix it"
            )
        ])
        
        # Mock _run_llm_review to return nothing
        agent._run_llm_review = AsyncMock(return_value=[])
        
        # Mock _run_fixer_loop to NOT change content (simulating stuck)
        agent._run_fixer_loop = AsyncMock(side_effect=lambda c, issues, context: c)
        
        # Run the agent (two iterations should detect stuck and set retry flag)
        # We allow 3 iterations in the agent loop.
        # Iteration 1: Advice A, Content C -> check_progress=True (recorded) -> fixer loop (no change)
        # Iteration 2: Advice A, Content C -> check_progress=False (STUCK) -> retry flag set -> break
        state, report, final_content = await agent.run_async(state, content, namespace)
            
        # Check if retry flag was set in loop_metadata
        self.assertTrue(state.loop_metadata.get(f"qa_retry_{namespace}"))
        
        # Check if the suggestion was enhanced for the next possible iteration
        # Note: the current run_async returns after max_iterations or if stuck twice.
        # In the first "stuck" detection, it updates issue suggestions.
        # Let's verify the issues in the report have the enhanced suggestion.
        found_backoff = False
        for issue in report.issues:
            if "PREVIOUS ATTEMPT FAILED" in issue.suggestion:
                found_backoff = True
                break
        self.assertTrue(found_backoff, "Backoff message should be injected into suggestions")

if __name__ == "__main__":
    unittest.main()
