import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState, AssetEntry, AssetSource, AssetFulfillmentAction
from src.agents.asset_management.models import VisualDirective
import asyncio

class TestAssetReuseLogic(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = AssetFulfillmentAgent(client=self.mock_client)
        
    @patch("src.agents.asset_management.fulfillment.AssetFulfillmentAgent._calculate_reuse_score")
    async def test_decide_fulfillment_strategy_reuse(self, mock_score):
        """Test that a score >= 90 results in USE_EXISTING."""
        mock_score.return_value = 95
        
        uar = MagicMock()
        asset = AssetEntry(id="a1", source=AssetSource.AI, semantic_label="test", local_path="p1")
        uar.assets = {"a1": asset}
        # In implementation, _query_uar_for_candidates returns list[AssetEntry]
        
        directive = VisualDirective(
            raw_block=":::visual ... :::", 
            start_pos=0, 
            end_pos=10,
            id="v1", 
            description="test intent", 
            action=AssetFulfillmentAction.GENERATE_SVG
        )
        
        with patch.object(self.agent, "_query_uar_for_candidates", return_value=[asset]):
            result_directive = await self.agent._decide_fulfillment_strategy(directive, uar)
        
        self.assertEqual(result_directive.action, AssetFulfillmentAction.USE_EXISTING)
        self.assertEqual(result_directive.matched_asset_id, "a1")

    @patch("src.agents.asset_management.fulfillment.AssetFulfillmentAgent._calculate_reuse_score")
    async def test_decide_fulfillment_strategy_create(self, mock_score):
        """Test that a score < 90 results in original action (GENERATE_SVG)."""
        mock_score.return_value = 80
        
        uar = MagicMock()
        asset = AssetEntry(id="a1", source=AssetSource.AI, semantic_label="test", local_path="p1")
        
        directive = VisualDirective(
            raw_block=":::visual ... :::", 
            start_pos=0, 
            end_pos=10,
            id="v1", 
            description="test intent", 
            action=AssetFulfillmentAction.GENERATE_SVG
        )
        
        with patch.object(self.agent, "_query_uar_for_candidates", return_value=[asset]):
            result_directive = await self.agent._decide_fulfillment_strategy(directive, uar)
        
        self.assertEqual(result_directive.action, AssetFulfillmentAction.GENERATE_SVG)

if __name__ == "__main__":
    unittest.main()