import unittest
import os
from pathlib import Path
import tempfile
import shutil
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.path_utils import get_project_root

class TestPathUtils(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_get_project_root_with_git(self):
        # Create a mock project structure
        git_dir = self.test_dir / ".git"
        git_dir.mkdir()
        
        sub_dir = self.test_dir / "a" / "b" / "c"
        sub_dir.mkdir(parents=True)
        
        # Test detection from sub_dir
        root = get_project_root(start_path=sub_dir)
        self.assertEqual(root.resolve(), self.test_dir.resolve())

    def test_get_project_root_with_manifest(self):
        # Create a mock project structure with manifest.json
        manifest = self.test_dir / "manifest.json"
        manifest.write_text("{}")
        
        sub_dir = self.test_dir / "x" / "y"
        sub_dir.mkdir(parents=True)
        
        # Test detection from sub_dir
        root = get_project_root(start_path=sub_dir)
        self.assertEqual(root.resolve(), self.test_dir.resolve())

    def test_get_project_root_fallback(self):
        # Without any anchor, it should eventually return the start path or system root
        # but our implementation should ideally have a fallback or raise error if nothing found
        # For now, let's just see what it does.
        root = get_project_root(start_path=self.test_dir)
        self.assertIsNotNone(root)

if __name__ == '__main__':
    unittest.main()
