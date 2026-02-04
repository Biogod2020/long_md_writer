import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.writer_agent import WriterAgent
from src.core.types import AgentState, AssetEntry, AssetSource, AssetPriority, UniversalAssetRegistry, Manifest, SectionInfo

class TestWriterVisual(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.generate_async = AsyncMock()
        self.agent = WriterAgent(client=self.mock_client)
        self.uar = UniversalAssetRegistry()
        
        # Create a mandatory asset with base64
        self.assigned_asset = AssetEntry(
            id="m-lead-ii",
            source=AssetSource.USER,
            priority=AssetPriority.MANDATORY,
            semantic_label="ECG Lead II schematic",
            base64_data="base64_lead_ii_image"
        )
        self.uar.assets[self.assigned_asset.id] = self.assigned_asset

    async def test_writer_multimodal_injection_in_prompt(self):
        """验证 WriterAgent 是否正确接收并引用了分配的图片"""
        section = SectionInfo(
            id="sec-1",
            title="The Heart Vector",
            summary="Sum",
            metadata={"assigned_assets": ["m-lead-ii"]}
        )
        
        state = AgentState(
            job_id="test_job",
            workspace_path=".",
            user_intent="Write about ECG.",
            manifest=Manifest(project_title="Title", description="Desc", sections=[section]),
            asset_registry=self.uar
        )
        
        self.mock_client.generate_async.return_value = MagicMock(
            success=True,
            text="Writing about Lead II based on the image..."
        )

        # We'll need to mock _save_section to avoid file IO errors in test
        with patch.object(self.agent, "_save_section", return_value="dummy_path"):
            await self.agent.run(state)

        # Verify prompt construction
        call_args = self.mock_client.generate_async.call_args
        parts = call_args[1]['parts']
        
        # 1. Check for multimodal parts (text + image)
        has_image = any(isinstance(p, dict) and "inline_data" in p and p["inline_data"]["data"] == "base64_lead_ii_image" for p in parts)
        has_instruction = any(isinstance(p, dict) and "text" in p and "m-lead-ii" in p["text"] for p in parts)
        
        self.assertTrue(has_image, "Writer should see the assigned mandatory image data.")
        self.assertTrue(has_instruction, "Writer should receive instruction to use the specific image.")

if __name__ == "__main__":
    unittest.main()
