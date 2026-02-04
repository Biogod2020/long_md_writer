import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.patcher import apply_smart_patch

class TestUniversalPatcher(unittest.TestCase):
    def test_exact_match(self):
        content = "line 1\nline 2\nline 3"
        search = "line 2"
        replace = "line 2 modified"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertEqual(result, "line 1\nline 2 modified\nline 3")

    def test_indentation_agnostic_match(self):
        # Target has 4 spaces, LLM provides 0 or different
        content = "def func():\n    print('hello')\n    return True"
        search = "print('hello')"
        replace = "print('hello world')"
        
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("    print('hello world')", result)
        
    def test_multiline_indentation_match(self):
        content = "if True:\n    line 1\n    line 2\n    line 3"
        # LLM provides less indentation
        search = "line 1\nline 2"
        replace = "line 1 modified\nline 2 modified"
        
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("    line 1 modified\n    line 2 modified", result)

    def test_fuzzy_match_minor_diff(self):
        content = "The quick brown fox jumps over the lazy dog"
        # LLM miscopies 'brown' as 'bron'
        search = "The quick bron fox"
        replace = "The fast brown fox"
        
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        # Note: fuzzy fallback might return slightly different result depending on DMP logic
        self.assertIn("The fast brown fox jumps", result)

    def test_no_match_fails(self):
        content = "completely different text"
        search = "not here"
        replace = "whatever"
        
        result, success = apply_smart_patch(content, search, replace)
        self.assertFalse(success)

    def test_multiline_fuzzy_match(self):
        content = """
def process_data(data):
    # This is a comment
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        # LLM miscopies comment and missing one space in result.append
        search = """# This is a commnt
    result = []
    for item in data:
       result.append(item * 2)"""
        
        replace = """# This is a fixed comment
    processed = []
    for item in data:
        processed.append(item * 2)"""
        
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("processed.append", result)
        self.assertNotIn("result.append", result)

    def test_indentation_plus_fuzzy(self):
        content = "    if value > 10:\n        print('too high')\n        return False"
        # LLM provides 0 indentation and miscopies 'print' as 'prnt'
        search = "if value > 10:\n    prnt('too high')"
        replace = "if value > 100:\n    print('way too high')"
        
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("    if value > 100:", result)
        self.assertIn("        print('way too high')", result)

if __name__ == "__main__":
    unittest.main()