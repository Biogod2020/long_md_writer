import unittest
from src.core.types import AssetEntry, AssetSource, AssetVQAStatus, CropMetadata
from pathlib import Path
import tempfile
import shutil
import json

class ModularAssetRegistry:
    """Refactored UAR supporting multiple mounted workspaces and a session-produced pool."""
    def __init__(self, session_path: str):
        self.session_path = Path(session_path)
        self.session_assets: dict[str, AssetEntry] = {}
        self.mounted_workspaces: dict[str, dict[str, AssetEntry]] = {}
        self.whitelisted_ids: set[str] = set()
        self.user_provided_ids: set[str] = set()

    def mount_workspace(self, name: str, assets_json_path: str):
        """Mount an external workspace library."""
        path = Path(assets_json_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assets = {}
            for aid, adata in data.get("assets", {}).items():
                # Simple mock loading logic for testing
                assets[aid] = AssetEntry(**adata)
            self.mounted_workspaces[name] = assets

    def add_to_whitelist(self, asset_id: str):
        self.whitelisted_ids.add(asset_id)

    def register_session_asset(self, entry: AssetEntry):
        self.session_assets[entry.id] = entry

    def get_all_candidates(self) -> list[AssetEntry]:
        """Merge all valid candidates into a single pool for processing."""
        candidates = []
        # 1. User Provided & Session Produced are always candidates
        candidates.extend(self.session_assets.values())
        
        # 2. Whitelisted assets from mounted workspaces
        for ws_assets in self.mounted_workspaces.values():
            for aid, asset in ws_assets.items():
                if aid in self.whitelisted_ids:
                    candidates.append(asset)
        
        return candidates

class TestModularUAR(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.session_dir = self.test_dir / "session"
        self.session_dir.mkdir()
        
        # Create a mock workspace
        self.ws_dir = self.test_dir / "ws1"
        self.ws_dir.mkdir()
        self.ws_json = self.ws_dir / "assets.json"
        
        mock_data = {
            "assets": {
                "ws1-asset-1": {
                    "id": "ws1-asset-1",
                    "source": "USER",
                    "semantic_label": "Global Diagram",
                    "local_path": "lib/1.png"
                }
            }
        }
        self.ws_json.write_text(json.dumps(mock_data))

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_merged_lookup(self):
        registry = ModularAssetRegistry(str(self.session_dir))
        registry.mount_workspace("anatomy", str(self.ws_json))
        
        # Register a session asset
        session_asset = AssetEntry(
            id="session-1",
            source="AI",
            semantic_label="Session Diagram",
            local_path="agent_generated/1.svg"
        )
        registry.register_session_asset(session_asset)
        
        # Whitelist the workspace asset
        registry.add_to_whitelist("ws1-asset-1")
        
        candidates = registry.get_all_candidates()
        ids = [c.id for c in candidates]
        
        self.assertIn("session-1", ids)
        self.assertIn("ws1-asset-1", ids)
        self.assertEqual(len(candidates), 2)

if __name__ == "__main__":
    unittest.main()
