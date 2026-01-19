import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.types import AgentState, AssetEntry, AssetSource, UniversalAssetRegistry
from src.agents.asset_management.indexer import AssetIndexerAgent
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
import asyncio
from pathlib import Path
import tempfile
import shutil
import json

class TestModularAssetE2E(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace_dir = self.test_dir / "workspace"
        self.workspace_dir.mkdir()
        
        # Create a mock external workspace
        self.lib_dir = self.test_dir / "data" / "asset_workspaces" / "anatomy"
        self.lib_dir.mkdir(parents=True)
        self.lib_json = self.lib_dir / "assets.json"
        
        mock_lib_data = {
            "assets": {
                "lib-heart": {
                    "id": "lib-heart",
                    "source": "USER",
                    "semantic_label": "Global Heart Diagram",
                    "local_path": "lib/heart.png"
                }
            }
        }
        self.lib_json.write_text(json.dumps(mock_lib_data))
        
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("builtins.input")
    @patch("src.agents.asset_management.fulfillment.AssetFulfillmentAgent._calculate_reuse_score")
    @patch("src.agents.asset_management.fulfillment.generate_svg_async")
    async def test_full_modular_flow(self, mock_gen_svg, mock_score, mock_input):
        """
        E2E Test:
        1. Mount 'anatomy' workspace.
        2. User selects 'lib-heart' manually.
        3. Chapter 1 generates a new 'lungs' diagram.
        4. Chapter 2 attempts to reuse 'lungs'.
        """
        state = AgentState(
            job_id="e2e_job",
            workspace_path=str(self.workspace_dir),
            user_intent="Writing a medical book."
        )
        uar = state.initialize_uar()
        uar.mount_workspace("anatomy", str(self.lib_json))
        
        # 1. Selection Phase
        # Inputs: 'n' (manual selection skip), 'n' (AI suggestions skip)
        # Wait, I want to manually select lib-heart
        mock_input.side_effect = ['y', '1', 'done', 'n'] # Manual selection 'y', choose '1', done, AI 'n'
        
        indexer = AssetIndexerAgent(client=self.mock_client)
        state = await indexer.run_async(state)
        
        self.assertIn("lib-heart", state.get_uar().whitelisted_ids)
        
        # 2. Fulfillment Chapter 1: Generate Lungs
        mock_score.return_value = 20 # No match
        mock_gen_svg.return_value = "<svg>lungs</svg>"
        
        fulfillment = AssetFulfillmentAgent(client=self.mock_client)
        content1 = ":::visual {\"id\": \"v-lungs\", \"description\": \"lungs diagram\"}\nContext\n:::"
        state, fulfilled1 = await fulfillment.run_async(state, content1, "s1")
        
        self.assertIn("v-lungs", state.get_uar().assets)
        
        # 3. Fulfillment Chapter 2: Reuse Lungs
        # Score for v-lungs intent against s1-produced asset should be high
        mock_score.return_value = 95
        
        content2 = ":::visual {\"id\": \"v-lungs-repeat\", \"description\": \"lungs diagram again\"}\nContext\n:::"
        state, fulfilled2 = await fulfillment.run_async(state, content2, "s2")
        
        self.assertIn('data-asset-id="v-lungs"', fulfilled2)
        # v-lungs should only be generated ONCE
        self.assertEqual(mock_gen_svg.call_count, 1)

if __name__ == "__main__":
    unittest.main()
