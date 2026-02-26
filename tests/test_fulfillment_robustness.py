
import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil
import os
import sys
import json

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState, AssetEntry, AssetSource, AssetFulfillmentAction
from src.agents.asset_management.models import VisualDirective

class TestFulfillmentRobustness(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace = self.test_dir / "workspace"
        self.workspace.mkdir()
        (self.workspace / "md").mkdir()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    async def _test_id_based_matching_async(self):
        """
        GIVEN a markdown file where a directive's text has been modified
        WHEN fulfillment runs
        THEN it should still correctly find the block by ID and replace it.
        """
        agent = AssetFulfillmentAgent(debug=True)
        
        # 1. Create a markdown file
        md_content = """# Chapter 1
Intro.

:::visual {"id": "s1-fig-1", "action": "GENERATE_SVG"}
ORIGINAL DESCRIPTION
:::

Outro.
"""
        md_path = self.workspace / "md" / "s1-sec-01.md"
        md_path.write_text(md_content, encoding="utf-8")
        
        # 2. Simulate Editorial modification in the file (but AgentState has old raw_block)
        modified_md_content = """# Chapter 1
Intro.

:::visual {"id": "s1-fig-1", "action": "GENERATE_SVG"}
MODIFIED DESCRIPTION BY EDITORIAL
:::

Outro.
"""
        md_path.write_text(modified_md_content, encoding="utf-8")
        
        # 3. Setup AgentState with the OLD raw_block captured earlier
        d = VisualDirective(
            id="s1-fig-1",
            raw_block=''':::visual {"id": "s1-fig-1", "action": "GENERATE_SVG"}
ORIGINAL DESCRIPTION
:::''',
            start_pos=0,
            end_pos=0
        )
        d.fulfilled = True
        d.result_html = "<figure>SUCCESSFUL_REPLACEMENT</figure>"
        
        state = AgentState(
            job_id="test_robustness",
            workspace_path=str(self.workspace),
            completed_md_sections=[str(md_path)]
        )
        
        import unittest.mock as mock
        
        # SOTA: Mock _check_asset_exists to avoid UAR lookup failure
        with mock.patch.object(agent, '_check_asset_exists', return_value=False):
            with mock.patch.object(agent, '_fulfill_directive_async', return_value=(d, None)):
                # Run the actual agent method
                await agent.run_parallel_async(state)
        
        # 4. Verify results
        final_content = md_path.read_text(encoding="utf-8")
        
        # Verification
        self.assertIn("<figure>SUCCESSFUL_REPLACEMENT</figure>", final_content)
        self.assertNotIn(":::visual", final_content)
        self.assertNotIn("MODIFIED DESCRIPTION", final_content)

    def test_id_based_matching(self):
        asyncio.run(self._test_id_based_matching_async())

if __name__ == '__main__':
    unittest.main()
