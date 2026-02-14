
import unittest
from src.core.patcher import apply_smart_patch

class TestUniversalPatcher(unittest.TestCase):
    def test_literal_match(self):
        content = "Line 1\nLine 2\nLine 3"
        search = "Line 2"
        replace = "Modified Line 2"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertEqual(result, "Line 1\nModified Line 2\nLine 3")

    def test_multiline_literal_match(self):
        content = "Header\nBody Start\nBody End\nFooter"
        search = "Body Start\nBody End"
        replace = "Body Mid"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertEqual(result, "Header\nBody Mid\nFooter")

    def test_indentation_matching(self):
        content = "def test():\n    # original code\n    print('hello')"
        search = "    # original code\n    print('hello')"
        replace = "    # new code\n    print('world')"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("    # new code", result)
        self.assertIn("    print('world')", result)

    def test_fuzzy_match_minor_diff(self):
        # Native fails due to 'extra space', Fuzzy should catch it
        content = "Line 1\n  Line 2 with space  \nLine 3"
        search = "Line 2 with space"
        replace = "Line 2 Fixed"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("Line 2 Fixed", result)

    def test_no_match_fails(self):
        content = "A B C"
        search = "X Y Z"
        replace = "1 2 3"
        result, success = apply_smart_patch(content, search, replace)
        self.assertFalse(success)
        self.assertIn("PATCH_FAILED", result)

    def test_empty_search_fails(self):
        content = "Some content"
        search = ""
        replace = "New content"
        result, success = apply_smart_patch(content, search, replace)
        self.assertFalse(success)
        self.assertIn("Search block is empty", result)

    def test_multiline_fuzzy_match(self):
        content = "First line\nSecond line with some slightly different text\nThird line"
        search = "Second line with some slightly diff text"
        replace = "Replaced middle"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("Replaced middle", result)

    def test_indentation_plus_fuzzy(self):
        content = "    if true:\n        do_something()\n        log_info()"
        search = "        do_something()\n        log_info_typo()" # typo
        replace = "        do_new_thing()"
        result, success = apply_smart_patch(content, search, replace)
        self.assertTrue(success)
        self.assertIn("        do_new_thing()", result)

if __name__ == "__main__":
    unittest.main()
