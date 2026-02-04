import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.patcher import apply_smart_patch

class StressTestPatcher(unittest.TestCase):
    def test_indentation_discrepancy(self):
        content = """
<div>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
</div>
"""
        # Search block with NO indentation
        search = """
<ul>
    <li>Item 1</li>
    <li>Item 2</li>
</ul>
"""
        replace = """
<ul>
    <li>Item 1 (Updated)</li>
    <li>Item 2 (Updated)</li>
</ul>
"""
        new_content, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("    <li>Item 1 (Updated)</li>", new_content)
        # Verify indentation was preserved (4 spaces for ul)
        self.assertIn("    <ul>", new_content)

    def test_whitespace_variations(self):
        content = "Line 1\n\nLine 2    \nLine 3"
        # AI might miss trailing spaces or exact newline count
        search = "Line 1\nLine 2\nLine 3"
        replace = "Line 1\nLine 2 (Fixed)\nLine 3"
        
        new_content, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("Line 2 (Fixed)", new_content)

    def test_partial_line_matching(self):
        content = "    <p>This is a long line with some content</p>"
        search = "<p>This is a long line"
        replace = "<p>This is a short line"
        
        new_content, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("<p>This is a short line with some content</p>", new_content)

if __name__ == "__main__":
    unittest.main()