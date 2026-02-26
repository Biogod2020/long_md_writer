import unittest
import asyncio
import time
from pathlib import Path
import tempfile
import shutil
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.asset_management.fulfillment import AssetFulfillmentAgent
from src.core.types import AgentState, AssetEntry, AssetSource, AssetFulfillmentAction
from src.agents.asset_management.models import VisualDirective

class TestFulfillmentStress(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace = self.test_dir / "workspace"
        self.workspace.mkdir()
        (self.workspace / "md").mkdir()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    async def _test_concurrency_deadlock_async(self):
        """
        Stress test for parallel fulfillment.
        Simulates many assets being fulfilled simultaneously.
        """
        agent = AssetFulfillmentAgent(max_concurrency=20, debug=True)
        
        # 1. Create a markdown file with many directives
        num_directives = 30
        directives_text = ""
        for i in range(num_directives):
            directives_text += f'\n:::visual {{"id": "fig-{i}", "action": "GENERATE_SVG"}}\nDescription {i}\n:::\n'
            
        md_content = f"# Stress Test\n{directives_text}"
        md_path = self.workspace / "md" / "s1-sec-01.md"
        md_path.write_text(md_content, encoding="utf-8")
        
        state = AgentState(
            job_id="stress_test",
            workspace_path=str(self.workspace),
            completed_md_sections=[str(md_path)]
        )
        
        # 2. Mock generation to be slow but successful
        import unittest.mock as mock
        
        async def mock_fulfill(d, *args, **kwargs):
            # Simulate some work
            await asyncio.sleep(0.1)
            d.fulfilled = True
            d.result_html = f"<figure>FIG-{d.id}</figure>"
            # Register in UAR to stress the lock
            asset = AssetEntry(
                id=d.id,
                source=AssetSource.AI,
                local_path=f"agent_generated/{d.id}.svg",
                semantic_label=f"Label {d.id}"
            )
            return d, asset

        with mock.patch.object(agent, '_fulfill_directive_async', side_effect=mock_fulfill):
            with mock.patch.object(agent, '_check_asset_exists', return_value=False):
                # Run parallel fulfillment
                try:
                    await asyncio.wait_for(agent.run_parallel_async(state), timeout=30)
                except asyncio.TimeoutError:
                    self.fail("Fulfillment DEADLOCKED or took too long!")

        # 3. Verify all were replaced
        final_content = md_path.read_text(encoding="utf-8")
        for i in range(num_directives):
            self.assertIn(f"<figure>FIG-fig-{i}</figure>", final_content)
        self.assertNotIn(":::visual", final_content)

    def test_concurrency_stress(self):
        asyncio.run(self._test_concurrency_deadlock_async())

if __name__ == '__main__':
    unittest.main()
