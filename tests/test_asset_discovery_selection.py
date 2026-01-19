import unittest
from unittest.mock import MagicMock, AsyncMock
from src.core.types import UniversalAssetRegistry, AssetEntry, AssetSource, AgentState
from src.agents.asset_management.indexer import AssetIndexerAgent
import asyncio
import json

class TestAssetDiscoverySelection(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.registry = UniversalAssetRegistry()
        # Mock a mounted workspace
        self.registry.mounted_workspaces["anatomy"] = {
            "a1": AssetEntry(id="a1", source=AssetSource.USER, semantic_label="Heart Diagram"),
            "a2": AssetEntry(id="a2", source=AssetSource.USER, semantic_label="Lungs Diagram"),
            "a3": AssetEntry(id="a3", source=AssetSource.USER, semantic_label="Brain Diagram")
        }

    async def test_tier1_broad_search_suggestions(self):
        """Test that the AI suggests relevant assets from the pool."""
        # Setup mock AI response
        self.mock_client.generate_async.return_value.success = True
        self.mock_client.generate_async.return_value.text = json.dumps({
            "suggestions": ["a1", "a2"],
            "reasons": "Relevant to cardiology and respiratory system."
        })
        
        # New selection logic implementation helper
        suggestions = await self._mock_run_tier1_filter("cardiovascular system", self.registry)
        
        self.assertIn("a1", suggestions)
        self.assertIn("a2", suggestions)
        self.assertNotIn("a3", suggestions)

    async def _mock_run_tier1_filter(self, user_intent: str, registry: UniversalAssetRegistry) -> list[str]:
        """Implementation logic for Tier 1 filter."""
        # This will be moved to AssetIndexerAgent or similar
        prompt = f"User Intent: {user_intent}\nCandidates: {list(registry.mounted_workspaces['anatomy'].keys())}"
        response = await self.mock_client.generate_async(prompt=prompt)
        data = json.loads(response.text)
        return data.get("suggestions", [])

if __name__ == "__main__":
    unittest.main()