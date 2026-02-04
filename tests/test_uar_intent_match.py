import unittest
from pathlib import Path
import tempfile
import shutil
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.types import UniversalAssetRegistry, AssetEntry, AssetSource, AssetQualityLevel
from src.core.gemini_client import GeminiClient

class TestUARIntentMatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.assets_json = self.test_dir / "assets.json"
        self.registry = UniversalAssetRegistry()
        self.registry.set_persist_path(str(self.assets_json))
        
        # Add some mock assets
        self.asset1 = AssetEntry(
            id="u-img-heart",
            source=AssetSource.USER,
            semantic_label="Anatomy of the human heart showing four chambers",
            local_path="assets/heart.png",
            quality_level=AssetQualityLevel.HIGH
        )
        self.asset2 = AssetEntry(
            id="u-img-brain",
            source=AssetSource.USER,
            semantic_label="Human brain anatomy lateral view",
            local_path="assets/brain.png",
            quality_level=AssetQualityLevel.HIGH
        )
        self.asset3 = AssetEntry(
            id="u-img-ecg",
            source=AssetSource.USER,
            semantic_label="Standard 12-lead ECG trace",
            local_path="assets/ecg.png",
            quality_level=AssetQualityLevel.MEDIUM
        )
        
        self.registry.register_immediate(self.asset1)
        self.registry.register_immediate(self.asset2)
        self.registry.register_immediate(self.asset3)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    async def test_intent_match_candidates_exists(self):
        """Verify that the method exists and can be called."""
        client = GeminiClient()
        query = "A diagram showing the heart chambers"
        try:
            candidates = await self.registry.intent_match_candidates_async(query, client=client, limit=2)
            self.assertIsNotNone(candidates)
            print(f"  [Test] Found {len(candidates)} candidates for '{query}'")
            for c in candidates:
                print(f"    - {c.id}: {c.semantic_label}")
        except AttributeError as e:
            self.fail(f"Method intent_match_candidates_async not implemented: {e}")

if __name__ == "__main__":
    unittest.main()
