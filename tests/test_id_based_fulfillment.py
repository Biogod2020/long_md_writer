import pytest
import re
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.agents.asset_management.models import VisualDirective

def test_id_based_matching_extreme():
    """
    Test that fulfillment succeeds even with:
    1. Multi-line JSON with unpredictable indentation.
    2. Single vs Double quotes.
    3. Newlines inside JSON values.
    4. LaTeX and special characters in description.
    """
    # 1. Target ID
    asset_id = "s1-fig-projection-fundamental"
    
    # 2. Simulate what Editorial QA might produce (The "Evil" block)
    # Note: Added extra spaces, newlines, and mixed quotes
    modified_content = f"""
## Section 1.1
Some text here.

:::visual {{
  'id' :
  "{asset_id}",
  "action": "GENERATE_SVG",
  "description": "A complex diagram with LaTeX: $V = P \\cdot L$ and 
  multi-line strings that might break
  simple regex."
}}
This is the body text inside the visual block.
It might also have $formula$ and "quotes".
:::

Final footer text.
"""
    
    # 3. Simulate directive object parsed from original (possibly different) content
    d = VisualDirective(raw_block="original block", start_pos=0, end_pos=10)
    d.id = asset_id
    d.fulfilled = True
    d.result_html = "<figure>SUCCESSFUL_INJECTION</figure>"
    
    # --- PROPOSED IMPROVED REGEX ---
    # We use a tempered greedy token to ensure we stay within the same block
    # and handles any whitespace/quote variation for the ID key and value.
    id_pattern = rf':::visual(?:(?!:::visual)[\s\S])*?["\']id["\']\s*:\s*["\']{re.escape(d.id)}["\'][\s\S]*?:::'
    
    # ACT
    match = re.search(id_pattern, modified_content, re.IGNORECASE)
    
    # ASSERT
    assert match is not None, f"Regex failed to match extreme case for ID: {d.id}"
    
    # Verify replacement doesn't break LaTeX backslashes
    final_content = re.sub(id_pattern, lambda _: d.result_html, modified_content, count=1, flags=re.IGNORECASE)
    
    assert "SUCCESSFUL_INJECTION" in final_content
    assert asset_id not in final_content
    assert "Some text here." in final_content
    assert "Final footer text." in final_content

if __name__ == "__main__":
    test_id_based_matching_extreme()
