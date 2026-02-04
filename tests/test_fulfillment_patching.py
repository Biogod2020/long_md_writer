import unittest
import re
from pathlib import Path

class TestFulfillmentPatching(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("workspace_test_patching")
        self.workspace.mkdir(exist_ok=True)

    def tearDown(self):
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def apply_fulfillment_logic(self, content, replacements):
        """
        Simulated logic for apply_fulfillment_to_file.
        replacements: dict mapping directive ID to replacement HTML.
        """
        pattern = r':::visual\s*\{([\s\S]*?)\}\s*([\s\S]*?):::'
        
        def replace_match(match):
            try:
                "{" + match.group(1) + "}"
                # Robust extraction might be needed if match.group(1) is partial
                # But here we assume the regex captures the JSON content.
                # Let's try to parse the whole block's config
                raw_config = match.group(1)
                if not raw_config.strip().startswith("{"):
                    # Handle cases where :::visual is followed by JSON directly
                    pass
                
                # For this test, we simplify: we look for ID in the raw config string
                # as the agent would do during fulfillment.
                import json
                try:
                    config = json.loads("{" + raw_config + "}" if not raw_config.strip().startswith("{") else raw_config)
                except:
                    # Fallback for the test regex group
                    config = json.loads(raw_config if raw_config.strip().startswith("{") else "{" + raw_config + "}")
                
                did = config.get("id")
                return replacements.get(did, match.group(0))
            except Exception as e:
                print(f"Error parsing in test: {e}")
                return match.group(0)

        return re.sub(pattern, replace_match, content)

    def test_inplace_replacement(self):
        content = """# Chapter 1
Intro text.

:::visual {"id": "fig-1", "action": "GENERATE_SVG"}
Description of fig 1
:::

Middle text.

:::visual {"id": "fig-2", "action": "SEARCH_WEB"}
Description of fig 2
:::

End text.
"""
        replacements = {
            "fig-1": '<figure><svg>...</svg></figure>',
            "fig-2": '<figure><img src="web.jpg"></figure>'
        }
        
        updated_content = self.apply_fulfillment_logic(content, replacements)
        
        self.assertIn('<figure><svg>...</svg></figure>', updated_content)
        self.assertIn('<figure><img src="web.jpg"></figure>', updated_content)
        self.assertIn('Intro text.', updated_content)
        self.assertIn('Middle text.', updated_content)
        self.assertIn('End text.', updated_content)
        self.assertNotIn(':::visual', updated_content)

if __name__ == "__main__":
    unittest.main()
