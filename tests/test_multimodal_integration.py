import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.types import AgentState, AssetEntry, AssetSource, AssetPriority, UniversalAssetRegistry, Manifest, SectionInfo
from src.agents.asset_management.indexer import AssetIndexerAgent
from src.agents.architect_agent import ArchitectAgent
from src.agents.writer_agent import WriterAgent
from src.agents.editorial_qa_agent import EditorialQAAgent
import asyncio
from pathlib import Path
import tempfile
import shutil
import json
import base64

class TestMultimodalIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.workspace_dir = self.test_dir / "workspace"
        self.workspace_dir.mkdir()
        self.inputs_dir = self.test_dir / "inputs"
        self.inputs_dir.mkdir()
        (self.inputs_dir / "mandatory").mkdir()
        
        # Create a dummy image
        self.img_path = self.inputs_dir / "mandatory" / "heart.png"
        self.img_path.write_bytes(b"fake_image_data")
        
        self.mock_client = MagicMock()
        self.mock_client.generate = MagicMock()
        self.mock_client.generate_async = AsyncMock()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    async def test_full_multimodal_chain(self):
        """
        Integration Test:
        1. Indexer finds 'heart.png' in mandatory folder.
        2. Architect assigns it to Section 1.
        3. Writer receives it and writes a draft.
        4. EditorialQA verifies it is present.
        """
        state = AgentState(
            job_id="integ_job",
            workspace_path=str(self.workspace_dir),
            user_intent="Write about heart anatomy."
        )
        
        # 1. Indexing
        indexer = AssetIndexerAgent(client=self.mock_client, input_dir=str(self.inputs_dir), skip_vision=True)
        # Mocking vision result
        with patch.object(indexer, "_process_image_async", wraps=indexer._process_image_async) as mock_proc:
            state = await indexer.run_async(state)
        
        uar = state.get_uar()
        asset_id = next(iter(uar.assets.keys()))
        self.assertEqual(uar.assets[asset_id].priority, AssetPriority.MANDATORY)
        
        # 2. Architecting
        architect = ArchitectAgent(client=self.mock_client)
        self.mock_client.generate.return_value = MagicMock(
            success=True,
            text=json.dumps({
                "project_title": "Heart",
                "description": "Desc",
                "sections": [{
                    "id": "sec-1", "title": "Ch1", "summary": "Sum",
                    "metadata": {"assigned_assets": [asset_id]}
                }]
            })
        )
        state = architect.run(state)
        self.assertIn(asset_id, state.manifest.sections[0].metadata["assigned_assets"])
        
        # 3. Writing
        writer = WriterAgent(client=self.mock_client)
        # Content correctly references the asset ID using the standard data-asset-id attribute
        self.mock_client.generate_async.return_value = MagicMock(
            success=True,
            text=f"Check this image: <img src='assets/heart.png' alt='Heart' data-asset-id='{asset_id}'>"
        )
        
        # We need to mock _save_section to actually write the file for EditorialQA
        def mock_save(s, sec, content):
            p = Path(s.workspace_path) / "md" / f"{sec.id}.md"
            p.parent.mkdir(exist_ok=True)
            p.write_text(content)
            return p
            
        with patch.object(writer, "_save_section", side_effect=mock_save):
            state = await writer.run(state)
            
        # 4. Editorial QA
        qa = EditorialQAAgent(client=self.mock_client)
        self.mock_client.generate_async.return_value = MagicMock(
            success=True,
            text='{"passed": true, "issues": [], "summary": "All good"}'
        )
        
        # EditorialQA node logic from workflow
        md_path = state.completed_md_sections[0]
        content = Path(md_path).read_text()
        print(f"\n[DEBUG] Asset ID: {asset_id}")
        print(f"[DEBUG] Content: {content}")
        state, report, updated = await qa.run_async(state, content, "s1")
        
        self.assertTrue(report.passed, f"QA should pass. Issues: {report.issues}")

if __name__ == "__main__":
    unittest.main()
