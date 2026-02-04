import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.types import UniversalAssetRegistry, AssetEntry, AssetSource, AssetFulfillmentAction
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.agents.asset_management.models import VisualDirective

class TestIntraSessionReuse(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = AssetFulfillmentAgent(client=self.mock_client)
        
        self.registry = UniversalAssetRegistry()
        # 1. Session Asset
        self.registry.assets["s1"] = AssetEntry(id="s1", source=AssetSource.AI, semantic_label="Session")
        # 2. Whitelisted Asset
        self.registry.mounted_workspaces["ws1"] = {
            "w1": AssetEntry(id="w1", source=AssetSource.USER, semantic_label="Whitelisted")
        }
        self.registry.whitelisted_ids.add("w1")

    async def test_unified_aggregation_lookup(self):
        """Test that all candidates are gathered for evaluation."""
        candidates = self.registry.get_all_candidates()
        ids = [c.id for c in candidates]
        
        self.assertIn("s1", ids)
        self.assertIn("w1", ids)
        self.assertEqual(len(candidates), 2)

    @patch("src.agents.asset_management.fulfillment.AssetFulfillmentAgent._calculate_reuse_score")
    async def test_decide_fulfillment_strategy_prioritization(self, mock_score):
        """Test that strategy considers all aggregated candidates."""
        # Setup scores
        mock_score.side_effect = [95, 80] # s1=95, w1=80
        
        directive = VisualDirective(
            raw_block=":::visual ... :::", 
            start_pos=0, end_pos=10,
            id="v1", description="test"
        )
        
        result = await self.agent._decide_fulfillment_strategy(directive, self.registry)
        
        self.assertEqual(result.action, AssetFulfillmentAction.USE_EXISTING)
        self.assertEqual(result.matched_asset_id, "s1")

if __name__ == "__main__":
    unittest.main()
