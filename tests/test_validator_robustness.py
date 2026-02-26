
import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.validators import MarkdownStructureValidator, ValidationSeverity

class TestValidatorRobustness(unittest.TestCase):
    def setUp(self):
        self.validator = MarkdownStructureValidator()

    def test_multiline_json_robustness(self):
        """
        Verify if the validator can handle multi-line JSON with extra spaces.
        """
        content = """# Section
:::visual {
  "id": "s1-fig-1",
  "action": "GENERATE_SVG",
  "description": "A complex
  description"
}
:::
"""
        result = self.validator.validate(content, expected_namespace="s1")
        
        # Print report for debugging
        print(result.to_report())
        
        # If the current validator is already robust, this will pass.
        # But we want to ensure it handles nested JSON-like strings or 
        # complex formatting that might trip up simple line-based logic.
        self.assertTrue(result.is_valid, f"Validator failed on multiline JSON:\n{result.to_report()}")

    def test_nested_containers_failure(self):
        """
        Current line-based logic might fail on nested ::: containers.
        """
        content = """:::important
Note this.
:::tip
A tip inside.
:::
End of tip.
:::
End of important.
"""
        # The current implementation uses a stack, so it *should* handle nesting,
        # but let's verify if it detects unclosed nested blocks correctly.
        result = self.validator.validate(content)
        print(result.to_report())
        self.assertTrue(result.is_valid)

    def test_unclosed_block(self):
        content = """# Section
:::visual {"id": "s1-fig-1"}
Content without closing tag
"""
        result = self.validator.validate(content)
        print(result.to_report())
        self.assertFalse(result.is_valid)
        self.assertIn("未正确闭合", result.issues[0].message)

    def test_invalid_json_in_block(self):
        content = """# Section
:::visual {"id": "s1-fig-1" MISSING_COMMA "action": "SVG"}
Content
:::
"""
        result = self.validator.validate(content)
        print(result.to_report())
        self.assertFalse(result.is_valid)
        self.assertIn("JSON 语法错误", result.issues[0].message)

if __name__ == '__main__':
    unittest.main()
