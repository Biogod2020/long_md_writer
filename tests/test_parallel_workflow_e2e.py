import unittest
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.gemini_client import GeminiClient, GeminiResponse

class TestParallelWorkflowE2E(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.workspace = Path("workspace_test_parallel")
        self.workspace.mkdir(exist_ok=True)
        (self.workspace / "md").mkdir(exist_ok=True)
        (self.workspace / "agent_generated").mkdir(exist_ok=True)
        (self.workspace / "agent_sourced").mkdir(exist_ok=True)
        
        self.mock_client = MagicMock(spec=GeminiClient)
        # Default mock response for SVG generation
        self.mock_client.generate_async = AsyncMock(return_value=GeminiResponse(
            success=True,
            text='```svg\n<svg><circle cx="50" cy="50" r="40" /></svg>\n```',
            thoughts="Generating a simple circle SVG."
        ))

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    async def test_batch_parallel_fulfillment(self):
        # 1. Setup State with 2 completed sections
        state = AgentState(
            job_id="test_batch",
            workspace_path=str(self.workspace),
            user_intent="test",
            manifest=Manifest(
                project_title="Test",
                description="Test",
                sections=[
                    SectionInfo(id="sec-1", title="Sec 1", summary="..."),
                    SectionInfo(id="sec-2", title="Sec 2", summary="...")
                ]
            )
        )
        
        # Write files with directives
        md1_path = self.workspace / "md" / "sec-1.md"
        md1_path.write_text("""# Section 1
Text A.
:::visual {"id": "s1-fig-1", "action": "GENERATE_SVG", "description": "Circle 1"}
Circle description
::: 
Text B.""", encoding="utf-8")

        md2_path = self.workspace / "md" / "sec-2.md"
        md2_path.write_text("""# Section 2
Text C.
:::visual {"id": "s2-fig-1", "action": "GENERATE_SVG", "description": "Circle 2"}
Circle description
::: 
Text D.""", encoding="utf-8")

        state.completed_md_sections = [str(md1_path), str(md2_path)]
        
        # 2. Run Parallel Fulfillment
        agent = AssetFulfillmentAgent(client=self.mock_client, skip_generation=False)
        # Mock audit_svg_visual_async to always pass to avoid repair loop complexity in this E2E
        with unittest.mock.patch('src.agents.asset_management.fulfillment.audit_svg_visual_async', 
                                 AsyncMock(return_value={"result": "pass", "overall_score": 100})):
            updated_state = await agent.run_parallel_async(state)
        
        # 3. Verify Results
        self.assertTrue(updated_state.batch_fulfillment_complete)
        self.assertEqual(len(updated_state.failed_directives), 0)
        
        # Verify in-place updates
        content1 = md1_path.read_text(encoding="utf-8")
        self.assertIn('<figure>', content1)
        self.assertIn('<img src="../agent_generated/s1-fig-1.svg"', content1)
        self.assertIn('data-asset-id="s1-fig-1"', content1)
        self.assertNotIn(':::visual', content1)
        
        content2 = md2_path.read_text(encoding="utf-8")
        self.assertIn('<figure>', content2)
        self.assertIn('<img src="../agent_generated/s2-fig-1.svg"', content2)
        self.assertIn('data-asset-id="s2-fig-1"', content2)
        self.assertNotIn(':::visual', content2)
        
        # Verify UAR
        uar = updated_state.get_uar()
        self.assertIn("s1-fig-1", uar.assets)
        self.assertIn("s2-fig-1", uar.assets)

if __name__ == "__main__":
    unittest.main()
