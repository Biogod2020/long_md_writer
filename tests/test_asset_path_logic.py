import unittest
from pathlib import Path
import tempfile
import shutil
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.types import AssetEntry, AssetSource, AssetQualityLevel
from src.core.path_utils import get_project_root

class TestAssetPathResolution(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp()).resolve()
        # Mock project root
        (self.test_dir / "manifest.json").write_text("{}")
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_get_absolute_path_workspace(self):
        """Verify resolution of assets within the workspace."""
        workspace = self.test_dir / "workspace" / "job1"
        workspace.mkdir(parents=True)
        
        asset_file = workspace / "agent_generated" / "fig1.svg"
        asset_file.parent.mkdir()
        asset_file.write_text("<svg></svg>")
        
        entry = AssetEntry(
            id="s1-fig1",
            source=AssetSource.AI,
            semantic_label="Test",
            local_path="agent_generated/fig1.svg"
        )
        
        abs_path = entry.get_absolute_path(workspace_path=workspace, project_root=self.test_dir)
        self.assertEqual(abs_path.resolve(), asset_file.resolve())

    def test_get_absolute_path_global(self):
        """Verify resolution of assets in global assets/ directory."""
        global_asset = self.test_dir / "assets" / "images" / "heart.png"
        global_asset.parent.mkdir(parents=True)
        global_asset.write_text("fake image data")
        
        entry = AssetEntry(
            id="u-heart",
            source=AssetSource.USER,
            semantic_label="Heart",
            local_path="assets/images/heart.png"
        )
        
        # Current workspace
        workspace = self.test_dir / "workspace" / "job1"
        workspace.mkdir(parents=True)
        
        abs_path = entry.get_absolute_path(workspace_path=workspace, project_root=self.test_dir)
        self.assertEqual(abs_path.resolve(), global_asset.resolve())

    def test_to_img_tag_relative_nested(self):
        """Test generating img tag from a nested markdown file."""
        workspace = self.test_dir / "workspace" / "job1"
        workspace.mkdir(parents=True)
        
        asset_file = workspace / "agent_generated" / "fig1.svg"
        asset_file.parent.mkdir()
        asset_file.write_text("<svg></svg>")
        
        entry = AssetEntry(
            id="s1-fig1",
            source=AssetSource.AI,
            semantic_label="Test SVG",
            local_path="agent_generated/fig1.svg"
        )
        
        # Target file: workspace/job1/md/sec-01.md
        target_md = workspace / "md" / "sec-01.md"
        target_md.parent.mkdir()
        
        img_tag = entry.to_img_tag(target_file=target_md, workspace_path=workspace)
        # Expected relative path from workspace/job1/md/ to workspace/job1/agent_generated/fig1.svg
        # is ../agent_generated/fig1.svg
        self.assertIn('src="../agent_generated/fig1.svg"', img_tag)

    def test_to_img_tag_global_asset(self):
        """Test generating img tag for a global asset from a nested file."""
        global_asset = self.test_dir / "assets" / "images" / "heart.png"
        global_asset.parent.mkdir(parents=True)
        global_asset.write_text("fake image data")
        
        entry = AssetEntry(
            id="u-heart",
            source=AssetSource.USER,
            semantic_label="Heart",
            local_path="assets/images/heart.png"
        )
        
        workspace = self.test_dir / "workspace" / "job1"
        workspace.mkdir(parents=True)
        target_md = workspace / "md" / "sec-01.md"
        target_md.parent.mkdir()
        
        # Mock project root via monkeypatch or parameter
        # For now let's just implement the logic to handle it if we pass it
        img_tag = entry.to_img_tag(target_file=target_md, workspace_path=workspace)
        
        # From workspace/job1/md/ to assets/images/heart.png
        # Path: ../../../assets/images/heart.png
        self.assertIn('src="../../../assets/images/heart.png"', img_tag)

    def test_to_img_tag_missing_asset(self):
        """Test generating img tag for a missing asset."""
        workspace = self.test_dir / "workspace" / "job1"
        workspace.mkdir(parents=True)
        target_md = workspace / "md" / "sec-01.md"
        target_md.parent.mkdir()
        
        entry = AssetEntry(
            id="missing-1",
            source=AssetSource.AI,
            semantic_label="Missing",
            local_path="not/found.png"
        )
        
        img_tag = entry.to_img_tag(target_file=target_md, workspace_path=workspace, project_root=self.test_dir)
        
        self.assertIn('<!-- ⚠️ FILE MISSING:', img_tag)
        self.assertIn('alt="FILE MISSING"', img_tag)

if __name__ == '__main__':
    unittest.main()
