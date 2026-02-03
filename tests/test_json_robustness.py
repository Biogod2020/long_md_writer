import unittest
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.json_utils import parse_json_dict_robust

class TestJsonRobustness(unittest.TestCase):
    
    def test_unescaped_latex(self):
        """测试包含未转义反斜杠的 LaTeX JSON (LLM 常见错误)"""
        # 模拟 LLM 产生的错误 JSON: \Phi 而不是 \\\\Phi
        raw_text = r'''
{
  "thought": "Fixing MathJax",
  "patches": [
    {
      "search": "V = \vec{P} \cdot \vec{L}",
      "replace": "V = \\Phi_{pos}"
    }
  ]
}
'''
        # 标准 json.loads 会在这里失败
        with self.assertRaises(json.JSONDecodeError):
            json.loads(raw_text)
            
        result = parse_json_dict_robust(raw_text)
        self.assertIn("patches", result)
        self.assertEqual(result["patches"][0]["search"], r"V = \vec{P} \cdot \vec{L}")
        self.assertEqual(result["patches"][0]["replace"], r"V = \Phi_{pos}")
        print("  ✅ Successfully parsed unescaped LaTeX backslashes")

    def test_mixed_escapes(self):
        """测试混合了正确转义和错误转义的 JSON"""
        raw_text = r'''
{
  "content": "Line 1\nLine 2 with \invalid escape and \\valid one"
}
'''
        # \n 是有效的，\\ 是有效的，但 \i 是无效的
        result = parse_json_dict_robust(raw_text)
        self.assertEqual(result["content"], "Line 1\nLine 2 with \\invalid escape and \\valid one")
        print("  ✅ Successfully handled mixed valid/invalid escapes")

    def test_complex_math_block(self):
        """测试实际场景中的复杂数学块"""
        raw_text = r'''
{
  "patches": [
    {
      "search": "$$$$V_{Lead}$$$$",
      "replace": "$V_{Lead}$"
    },
    {
      "search": "$$$$\\Phi$$$$",
      "replace": "$\\Phi$"
    }
  ]
}
'''
        result = parse_json_dict_robust(raw_text)
        self.assertEqual(len(result["patches"]), 2)
        self.assertEqual(result["patches"][1]["search"], r"$$$$\Phi$$$$")
        print("  ✅ Successfully parsed complex MathJax search/replace block")

if __name__ == "__main__":
    unittest.main()
