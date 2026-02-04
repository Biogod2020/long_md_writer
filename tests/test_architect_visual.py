import unittest
from unittest.mock import MagicMock
from src.agents.architect_agent import ArchitectAgent
from src.core.types import AgentState, AssetEntry, AssetSource, AssetPriority, UniversalAssetRegistry
import json

class TestArchitectVisual(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.agent = ArchitectAgent(client=self.mock_client)
        self.uar = UniversalAssetRegistry()
        
        # Create a mandatory asset with base64
        self.mandatory_asset = AssetEntry(
            id="m-heart-1",
            source=AssetSource.USER,
            priority=AssetPriority.MANDATORY,
            semantic_label="A detailed heart diagram",
            base64_data="dummy_base64_string"
        )
        self.uar.assets[self.mandatory_asset.id] = self.mandatory_asset

    def test_architect_visual_assignment_in_prompt(self):
        """验证 ArchitectAgent 的提示词是否包含了强制性图片信息"""
        state = AgentState(
            job_id="test_job",
            workspace_path=".",
            user_intent="Write about heart anatomy.",
            asset_registry=self.uar
        )
        
        # Mock successful generation
        self.mock_client.generate.return_value = MagicMock(
            success=True,
            text=json.dumps({
                "project_title": "Heart Book",
                "description": "Desc",
                "sections": [
                    {
                        "id": "sec-1",
                        "title": "Intro",
                        "summary": "Intro sum",
                        "metadata": {"assigned_assets": ["m-heart-1"]}
                    }
                ]
            })
        )

        self.agent.run(state)

        # Verify prompt construction
        call_args = self.mock_client.generate.call_args
        parts = call_args[1]['parts']
        
        # Check if multimodal parts contain the image
        has_image = any(isinstance(p, dict) and "inline_data" in p for p in parts)
        has_text_instruction = any(isinstance(p, dict) and "text" in p and "Required Assets" in p["text"] for p in parts)
        
        # Since I haven't updated _build_prompt_parts yet, these might fail
        # But this is the TDD way.
        self.assertTrue(has_image, "Prompt should contain the mandatory image data.")
        self.assertTrue(has_text_instruction, "Prompt should contain instructions for mandatory assets.")

if __name__ == "__main__":
    unittest.main()
