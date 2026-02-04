import unittest
from unittest.mock import MagicMock, AsyncMock
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AssetEntry, AssetSource

class TestAssetReuseScoring(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = AssetFulfillmentAgent(client=self.mock_client)
        
    async def test_calculate_reuse_score_high_match(self):
        """Test that a semantically identical description returns a high score."""
        # Mock LLM to return a high score
        self.mock_client.generate_async.return_value.success = True
        self.mock_client.generate_async.return_value.text = '{"score": 95, "reason": "Exact semantic match."}'
        
        intent = "A red square representing a heart valve."
        existing_asset = AssetEntry(
            id="asset_01",
            source=AssetSource.USER,
            local_path="assets/red_square.png",
            semantic_label="A red square used for heart valve diagrams.",
            tags=["medical", "heart"]
        )
        
        score = await self.agent._calculate_reuse_score(intent, existing_asset)
        self.assertEqual(score, 95)
        
    async def test_calculate_reuse_score_low_match(self):
        """Test that a different description returns a low score."""
        self.mock_client.generate_async.return_value.success = True
        self.mock_client.generate_async.return_value.text = '{"score": 20, "reason": "Different shape and purpose."}'
        
        intent = "A blue circle representing a lung."
        existing_asset = AssetEntry(
            id="asset_01",
            source=AssetSource.USER,
            local_path="assets/red_square.png",
            semantic_label="A red square.",
            tags=["medical"]
        )
        
        score = await self.agent._calculate_reuse_score(intent, existing_asset)
        self.assertEqual(score, 20)

if __name__ == "__main__":
    unittest.main()