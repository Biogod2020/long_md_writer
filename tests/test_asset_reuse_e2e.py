import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState, AssetEntry, AssetSource, UniversalAssetRegistry
from pathlib import Path
import tempfile
import shutil

class TestAssetReuseE2E(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = AssetFulfillmentAgent(client=self.mock_client)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    @patch("src.agents.asset_management.fulfillment.AssetFulfillmentAgent._calculate_reuse_score")
    @patch("src.agents.asset_management.fulfillment.generate_svg_async")
    async def test_e2e_reuse_flow(self, mock_gen_svg, mock_score):
        """
        E2E Scenario:
        1. Section has two :::visual blocks.
        2. UAR already has one asset that matches the first block (>90).
        3. Second block does not match any existing asset (<90).
        4. Expected: First block reuses asset, second block triggers generation.
        """
        # Setup UAR
        uar_path = self.test_dir / "assets.json"
        uar = UniversalAssetRegistry()
        uar.set_persist_path(str(uar_path))
        
        existing_asset = AssetEntry(
            id="existing_svg",
            source=AssetSource.AI,
            local_path="generated_assets/existing_svg.svg",
            semantic_label="A red heart diagram",
            tags=["medical", "heart"]
        )
        uar.register_immediate(existing_asset)
        
        # Mock Scoring
        # First intent (matches existing) -> 95
        # Second intent (new) -> 20
        mock_score.side_effect = [95, 20]
        
        # Mock SVG Generation for the second one
        mock_gen_svg.return_value = "<svg>new</svg>"
        
        state = AgentState(
            job_id="test_e2e",
            workspace_path=str(self.test_dir),
            asset_registry=uar
        )
        
        content = """
# Chapter 1
Here is a heart:
:::visual {"id": "v1", "description": "A heart diagram"}
Context
:::

And here is a lung:
:::visual {"id": "v2", "description": "A lung diagram"}
Context
:::
"""
        
        # Run
        new_state, fulfilled_content = await self.agent.run_async(state, content, "s1")
        
        # Verify
        # 1. v1 should be replaced by existing_svg HTML
        self.assertIn('data-asset-id="existing_svg"', fulfilled_content)
        # 2. v2 should be replaced by a new asset ID (v2)
        self.assertIn('data-asset-id="v2"', fulfilled_content)
        # 3. New asset should be in UAR
        self.assertIn("v2", uar.assets)
        # 4. Generate SVG should have been called once
        mock_gen_svg.assert_called_once()

if __name__ == "__main__":
    unittest.main()
