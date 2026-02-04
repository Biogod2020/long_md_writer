import unittest
from pathlib import Path
import tempfile
import shutil
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.types import AgentState, Manifest, SectionInfo
from src.agents.asset_management.fulfillment import AssetFulfillmentAgent

class TestFulfillmentObservability(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace = self.test_dir / "workspace"
        self.workspace.mkdir()
        self.md_dir = self.workspace / "md"
        self.md_dir.mkdir()
        
        # Create a mock MD file with a directive that will fail
        self.md_file = self.md_dir / "test.md"
        self.md_file.write_text("""
# Test
:::visual {"id": "v1", "action": "GENERATE_SVG", "description": "Crash Me"}
Content
:::
""", encoding="utf-8")
        
        self.state = AgentState(
            job_id="test_job",
            workspace_path=str(self.workspace),
            completed_md_sections=[str(self.md_file)]
        )
        self.state.manifest = Manifest(
            project_title="Test",
            description="Test",
            sections=[SectionInfo(id="sec-1", title="Test", summary="Test")]
        )
        self.state.initialize_uar()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    async def test_failure_reporting_structure(self):
        """Verify that failed directives have enriched metadata."""
        # Mock fulfillment to fail
        agent = AssetFulfillmentAgent(client=None) # No client, will crash on generation
        
        # Override _fulfill_directive_async to raise exception
        async def mock_fail(*args, **kwargs):
            raise ValueError("Simulated Fulfillment Crash")
        
        agent._fulfill_directive_async = mock_fail
        
        updated_state = await agent.run_parallel_async(self.state)
        
        self.assertTrue(len(updated_state.failed_directives) > 0)
        failure = updated_state.failed_directives[0]
        
        print(f"\n  [Test] Failure Structure: {json.dumps(failure, indent=2, ensure_ascii=False)}")
        
        self.assertIn("id", failure)
        self.assertIn("description", failure)
        self.assertIn("action", failure)
        self.assertIn("context_preview", failure)
        self.assertEqual(failure["error"], "Simulated Fulfillment Crash")
        
        # Check trace file
        debug_dir = self.workspace / "fulfillment_debug"
        trace_file = debug_dir / "v1_trace.json"
        self.assertTrue(trace_file.exists())
        trace_data = json.loads(trace_file.read_text(encoding="utf-8"))
        self.assertIn("error", trace_data)
        self.assertIn("Traceback", trace_data["error"])

if __name__ == "__main__":
    unittest.main()
