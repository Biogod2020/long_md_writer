import pytest
from src.core.validators import MarkdownStructureValidator

def test_validator_extreme_stress():
    validator = MarkdownStructureValidator()
    
    # 1. Complex mixed containers (Data + Presentational)
    content = """
:::important
This is an important note.
:::
:::visual
{
  "id": "s1-fig-01",
  "action": "GENERATE_SVG"
}
:::
:::tip
Remember to use $E=mc^2$.
:::
:::formula-block
$$ x = y $$
:::
"""
    result = validator.validate(content)
    assert result.is_valid, f"Failed on basic mixed containers: {result.to_report()}"

    # 2. Evil Nested Braces inside JSON (Stress JSON robustness)
    content = """
:::visual
{
  "id": "s1-evil-braces",
  "config": {
     "nested": [1, 2, 3],
     "text": "contains } braces { and extra ::: markers"
  }
}
:::
"""
    result = validator.validate(content)
    assert result.is_valid, f"Failed on nested braces/text: {result.to_report()}"

    # 3. Malformed presentational (should still be valid as we don't audit content)
    # But it must be BALANCED.
    content = """
:::unknown-plugin
Some random data here.
:::
"""
    result = validator.validate(content)
    assert result.is_valid, "Should handle unknown container names as long as they are balanced"

    # 4. Deeply nested presentational
    content = """
:::outer
  :::inner
    Content
  :::
:::
"""
    result = validator.validate(content)
    assert result.is_valid, "Should handle nested generic containers"

    # 5. Extreme whitespace and weird IDs
    content = """
:::visual    
    {
        "id"   :    "s1-spaced-id"   ,
        "action": "GENERATE_SVG"
    }
    
:::
"""
    result = validator.validate(content, expected_namespace="s1")
    assert result.is_valid, f"Failed on extreme JSON whitespace: {result.to_report()}"

    # 6. FAIL CASE: Unclosed container
    content = """:::visual
{"id":"test"}"""
    result = validator.validate(content)
    assert not result.is_valid
    assert "未正确闭合" in result.issues[0].message

    # 7. FAIL CASE: Isolated marker
    content = """Some text
:::
More text"""
    result = validator.validate(content)
    assert not result.is_valid
    assert "孤立或多余" in result.issues[0].message

    # 8. FAIL CASE: Missing ID in data directive
    content = """:::visual
{"action":"GENERATE_SVG"}
:::"""
    result = validator.validate(content)
    assert not result.is_valid
    assert "缺少必需字段 'id'" in result.issues[0].message

    # 9. FAIL CASE: Namespace mismatch
    content = """:::visual
{"id":"s2-wrong-ns"}
:::"""
    result = validator.validate(content, expected_namespace="s1")
    assert not result.is_valid
    assert "缺少前缀 's1-'" in result.issues[0].message

    print("✅ All extreme validator stress tests passed!")

if __name__ == "__main__":
    test_validator_extreme_stress()
