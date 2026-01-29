import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.editorial_qa_agent import EditorialQAAgent, QASeverity, QAIssue, QAIssueType
from src.core.types import AgentState

class TestEditorialQAStuck(unittest.IsolatedAsyncioTestCase):
    async def test_run_async_stuck_detection(self):
        client = MagicMock()
        agent = EditorialQAAgent(client=client)
        
        state = AgentState(job_id="test", workspace_path=".")
        content = "Test content"
        namespace = "s1"
        
        # Mock _run_local_checks to return an error
        agent._run_local_checks = MagicMock(return_value=[
            QAIssue(QAIssueType.SEMANTIC_DRIFT, QASeverity.ERROR, "loc", "STUCK ISSUE", "fix it")
        ])
        
        # Mock LLM review to be empty
        agent._run_llm_review = AsyncMock(return_value=[])
        
        # Mock fixer loop to return SAME content (simulate failed fix)
        agent._run_fixer_loop = AsyncMock(return_value=content)
        
        # Execute
        state, report, final_content = await agent.run_async(state, content, namespace)
        
        # Should break loop due to stuck detection
        # max_iterations is 3, but if it's stuck it should break at Iteration 2
        # Actually check_progress returns False if seen twice
        
        print(f"QA Iterations performed: {len(agent._run_local_checks.call_args_list)}")
        self.assertLess(len(agent._run_local_checks.call_args_list), 3)

if __name__ == "__main__":
    asyncio.run(unittest.main())
