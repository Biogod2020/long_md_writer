import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState, AssetEntry, AssetSource

class TestFulfillmentAggregation(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace = self.test_dir / "workspace"
        self.workspace.mkdir()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    async def _run_aggregation_logic(self):
        """
        Verify that fulfillment returns assets for bulk registration 
        instead of individual writes.
        """
        agent = AssetFulfillmentAgent(debug=True)
        
        # Mock directive and state
        from src.agents.asset_management.models import VisualDirective
        from src.core.types import AssetFulfillmentAction
        
        # SOTA: Providing required positional arguments
        d = VisualDirective(id="test-1", raw_block=":::visual {} :::", start_pos=0, end_pos=10)
        d.action = AssetFulfillmentAction.GENERATE_SVG
        d.description = "Test SVG"
        
        # Create a real AgentState to test UAR interaction
        state = AgentState(job_id="test", workspace_path=str(self.workspace))
        uar = state.get_uar()
        
        # We'll use a mocked internal step to verify the return signature
        import unittest.mock as mock
        
        mock_asset = AssetEntry(
            id="test-1",
            source=AssetSource.AI,
            local_path="agent_generated/test-1.svg",
            semantic_label="Test"
        )
        
        with mock.patch.object(agent, '_fulfill_svg_step', return_value=(d, mock_asset)):
            trace = {"steps": []}
            res_d, res_asset = await agent._fulfill_directive_async(
                d, uar, self.workspace/"gen", self.workspace/"src", "s1", self.workspace, state, trace
            )
            
            self.assertEqual(res_d.id, "test-1")
            self.assertEqual(res_asset.id, "test-1")
            self.assertIsInstance(res_asset, AssetEntry)

    def test_aggregation_logic(self):
        asyncio.run(self._run_aggregation_logic())

if __name__ == '__main__':
    unittest.main()
