import unittest
import os
from pathlib import Path
import base64
import tempfile
import shutil
from src.core.types import AgentState
from src.core.gemini_client import GeminiClient
from src.agents.asset_management.indexer import AssetIndexerAgent
from src.agents.architect_agent import ArchitectAgent
from src.agents.writer_agent import WriterAgent
from src.agents.editorial_qa_agent import EditorialQAAgent

class TestMultimodalRealAPI(unittest.IsolatedAsyncioTestCase):
    """
    Real-world Integration Test for Multimodal Intent-Layered Asset Management.
    Uses local geminicli2api proxy (no mocks).
    """
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace_dir = self.test_dir / "workspace"
        self.workspace_dir.mkdir()
        self.inputs_dir = self.test_dir / "inputs"
        self.inputs_dir.mkdir()
        (self.inputs_dir / "mandatory").mkdir()
        
        # Create a real small image (1x1 red pixel) to test multimodal injection
        # Using a simple red dot PNG base64
        red_dot_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        self.img_path = self.inputs_dir / "mandatory" / "red_dot.png"
        self.img_path.write_bytes(base64.b64decode(red_dot_base64))
        
        # Ensure client points to local proxy
        self.client = GeminiClient(
            api_base_url="http://localhost:8888/v1",
            auth_token=os.getenv("GEMINI_AUTH_PASSWORD", "123456"),
            model="gemini-3-flash-preview" # Use flash for faster/cheaper tests
        )

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    async def test_full_multimodal_chain_live(self):
        print("\n[LIVE TEST] Starting Multimodal Chain with Real API...")
        
        state = AgentState(
            job_id="live_integ_job",
            workspace_path=str(self.workspace_dir),
            user_intent="Write a single paragraph explaining a red dot image. The image is mandatory."
        )
        
        # 1. Indexing (Real API for analysis)
        print("[1/4] Indexing mandatory assets...")
        indexer = AssetIndexerAgent(client=self.client, input_dir=str(self.inputs_dir))
        state = await indexer.run_async(state)
        
        uar = state.get_uar()
        self.assertEqual(len(uar.assets), 1)
        asset_id = next(iter(uar.assets.keys()))
        print(f"      ✓ Asset Indexed: {asset_id} (Priority: {uar.assets[asset_id].priority})")
        
        # 2. Architecting (Real API for planning)
        print("[2/4] Planning with Architect...")
        architect = ArchitectAgent(client=self.client)
        # Note: run() is sync, uses asyncio.run internally or provided loop. 
        # Since we are in IsolatedAsyncioTestCase, we should use run_async if available.
        state = await architect.run_async(state)
        
        has_assignment = any(asset_id in sec.metadata.get("assigned_assets", []) for sec in state.manifest.sections)
        self.assertTrue(has_assignment, "Architect must assign the mandatory asset.")
        print(f"      ✓ Manifest generated. Sections: {len(state.manifest.sections)}")
        
        # 3. Writing (Real API multimodal writing)
        print("[3/4] Writing with Multimodal Writer...")
        writer = WriterAgent(client=self.client)
        # We only run for the first section
        state = await writer.run(state)
        
        md_path = Path(state.completed_md_sections[0])
        content = md_path.read_text()
        print(f"      ✓ Section written ({len(content)} chars)")
        # Check if asset_id is mentioned in data-asset-id
        self.assertIn(asset_id, content, "Writer should have included the asset ID in the text.")
        
        # 4. Editorial QA (Real API for verification)
        print("[4/4] Verifying with Editorial QA...")
        # Use strict_mode=False so warnings don't fail the test
        qa = EditorialQAAgent(client=self.client, strict_mode=False)
        namespace = "s1"
        state, report, updated_content = await qa.run_async(state, content, namespace)
        
        print(f"      ✓ QA Passed: {report.passed}")
        if report.issues:
            print(f"      ℹ QA Issues Found: {len(report.issues)}")
            for issue in report.issues:
                print(f"        - [{issue.severity.value}] {issue.message}")
            
        self.assertTrue(report.passed, "Final product should pass QA audit (ignoring warnings).")

        # 5. Visual Verification (Playwright)
        print("[5/5] Visual Verification...")
        from src.agents.visual_qa.renderer import PlaywrightRenderer
        renderer = PlaywrightRenderer(output_dir=self.test_dir / "visual_verify")
        # Ensure updated_content is used
        snapshot_path = await renderer.render_to_image(updated_content, "final_verify")
        print(f"      ✓ Visual Snapshot generated: {snapshot_path}")
        self.assertTrue(snapshot_path.exists())

if __name__ == "__main__":
    unittest.main()
