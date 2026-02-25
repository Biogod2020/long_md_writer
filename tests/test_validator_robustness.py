import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.validators import MarkdownStructureValidator

class TestValidatorRobustness(unittest.TestCase):
    
    def setUp(self):
        self.validator = MarkdownStructureValidator()

    def test_multi_line_json_config(self):
        """用例 1: 故障重现 - :::visual 块包含多行 JSON 配置"""
        content = """
# Test Section

:::visual
{
  "id": "s1-fig-dipole-model",
  "action": "sourcing",
  "description": "A dipole model of the heart"
}
:::

Some text.
"""
        result = self.validator.validate(content)
        # 预期失败: 当前校验器会报错说“缺少必要的 JSON 配置”或“后缀不是合法的 JSON 格式”
        self.assertTrue(result.is_valid, f"Validator should accept multi-line JSON. Issues: {result.to_report()}")

    def test_extreme_layout(self):
        """用例 2: 极端排版 - 包含大量冗余空格和空行"""
        content = """
:::visual   
    
{
    "id": "s1-fig-complex",
    
    "action": "sourcing",
    
    "description": "Complex layout test"
}

:::
"""
        result = self.validator.validate(content)
        self.assertTrue(result.is_valid, f"Validator should handle extreme layouts. Issues: {result.to_report()}")

    def test_strict_id_namespace(self):
        """用例 4: 核心规范 - 命名空间前缀错误"""
        content_wrong_ns = """
:::visual
{
  "id": "wrong-fig-1",
  "action": "sourcing",
  "description": "Wrong namespace"
}
:::
"""
        # 期望前缀是 s1-
        result = self.validator.validate(content_wrong_ns, expected_namespace="s1")
        self.assertFalse(result.is_valid, "Validator should fail when namespace prefix is wrong.")
        self.assertIn("缺少命名空间前缀 's1-'", result.to_report())

    def test_correct_id_namespace(self):
        """用例 5: 核心规范 - 正确的命名空间前缀"""
        content_correct = """
:::visual
{
  "id": "s1-fig-1",
  "action": "sourcing",
  "description": "Correct namespace"
}
:::
"""
        result = self.validator.validate(content_correct, expected_namespace="s1")
        self.assertTrue(result.is_valid, f"Validator should pass with correct namespace. Issues: {result.to_report()}")

    def test_mixed_single_and_multi_line(self):
        """混合单行和多行块"""
        content = """
:::visual {"id": "s1-fig-1", "action": "sourcing", "description": "Single line"}
:::

:::visual
{
  "id": "s1-fig-2",
  "action": "sourcing",
  "description": "Multi line"
}
:::
"""
        result = self.validator.validate(content)
        self.assertTrue(result.is_valid, f"Validator should handle mixed single/multi line blocks. Issues: {result.to_report()}")

    def test_stress_large_file(self):
        """压力测试 1: 处理包含 500 个视觉块的大规模文件"""
        blocks = []
        for i in range(500):
            blocks.append(f"""
## Section {i}
:::visual
{{
  "id": "s1-fig-{i}",
  "action": "sourcing",
  "description": "Massive test image {i}"
}}
:::
""")
        content = "\n".join(blocks)
        result = self.validator.validate(content, expected_namespace="s1")
        self.assertTrue(result.is_valid, "Validator should handle large files efficiently.")
        self.assertEqual(len([iss for iss in result.issues if iss.severity == "ERROR"]), 0)

    def test_stress_malformed_closures(self):
        """压力测试 2: 真正未闭合的块与审计失败"""
        content = """
:::visual
{
  "id": "s1-fig-unclosed",
  "description": "This block starts but never ends...
  
  Wait, I'm just adding text here.
  No triple-colon-end till the end of string.
"""
        result = self.validator.validate(content, expected_namespace="s1")
        # 预期：检测到未闭合错误
        errors = [iss.message for iss in result.issues if "未正确闭合" in iss.message]
        self.assertTrue(len(errors) > 0, "Should detect unclosed blocks at EOF.")

    def test_accidental_closure_audit_failure(self):
        """测试：因干扰导致提前闭合时，JSON 审计应拦截非法内容"""
        content = """
:::visual
{
  "id": "s1-fig-broken",
  "description": "Accidental closure coming..."

:::important
This text is now inside the visual buffer.
:::
"""
        # 这里的 ::: 会关闭 visual 块，但由于 buffer 里的 JSON 不完整，审计应报错。
        result = self.validator.validate(content, expected_namespace="s1")
        self.assertFalse(result.is_valid)
        self.assertTrue(any("JSON 语法错误" in iss.message for iss in result.issues))

    def test_stress_extreme_chars_and_long_lines(self):
        """压力测试 3: 极端字符与超长行"""
        long_str = "A" * 10000
        content = f"""
:::visual
{{
  "id": "s1-fig-long",
  "action": "sourcing",
  "description": "Long string: {long_str}",
  "metadata": "🚀🧬中国_Standard_Test_!@#$%^&*()_+\u4e2d\u6587"
}}
:::
"""
        result = self.validator.validate(content, expected_namespace="s1")
        self.assertTrue(result.is_valid, "Validator should handle non-ASCII and very long lines.")

    def test_unbalanced_data_directives(self):
        """测试数据指令的不平衡嵌套（虽然不合法但不应崩溃）"""
        content = """
:::visual
{ "id": "s1-v1" }
:::visual
{ "id": "s1-v2" }
:::
:::
"""
        # 这种情况下，第一个 visual 会收集内容直到遇到第一个 :::
        # 内部包含了另一个指令标记，由于提取逻辑是 extract_json_from_text，
        # 它应该能在缓冲区内找到合适的 JSON 对象。
        result = self.validator.validate(content, expected_namespace="s1")
        # 只要不崩溃，并且逻辑符合目前的 Parser 即可。
        # 这种嵌套在 Markdown 中不合法，校验器应该通过报错或审计来识别。
        print(f"  Captured report for unbalanced nesting: {result.to_report()}")

if __name__ == "__main__":
    unittest.main()
