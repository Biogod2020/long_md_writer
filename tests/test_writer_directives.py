import unittest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from src.agents.writer_agent import WriterAgent
from src.core.types import AgentState, Manifest, SectionInfo, UniversalAssetRegistry, AssetEntry, AssetSource
from src.core.gemini_client import GeminiClient, GeminiResponse

class TestWriterDirectives(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=GeminiClient)
        self.agent = WriterAgent(client=self.mock_client)
        self.workspace = Path("workspace_test_directives")
        self.workspace.mkdir(exist_ok=True)
        (self.workspace / "md").mkdir(exist_ok=True)

    def tearDown(self):
        import shutil
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    async def test_writer_emits_reuse_score(self):
        """Verify that the writer can produce the new :::visual format with reuse_score."""
        state = AgentState(
            job_id="test_job",
            workspace_path=str(self.workspace),
            user_intent="Write a section about heart anatomy.",
            manifest=Manifest(
                project_title="Heart Guide",
                description="Technical guide",
                sections=[SectionInfo(id="sec-1", title="Anatomy", summary="Basic structure")]
            )
        )
        
        # Mock UAR with an existing asset
        uar = state.initialize_uar()
        asset = AssetEntry(
            id="u-img-heart-1",
            source=AssetSource.USER,
            semantic_label="Cross-section of a human heart",
            local_path="assets/images/heart.jpg"
        )
        uar.register_immediate(asset)

        # Mock AI response containing the new directive format
        new_format_content = """
Here is the heart anatomy.

:::visual {"id": "s1-fig-heart", "action": "USE_EXISTING", "matched_asset": "u-img-heart-1", "reuse_score": 95, "reason": "Perfectly matches the required anatomical view.", "description": "Human heart cross-section"}
The diagram above shows the four chambers of the heart.
:::
"""
        self.mock_client.generate_async = AsyncMock(return_value=GeminiResponse(
            success=True,
            text=new_format_content,
            thoughts="I decided to reuse the existing heart image."
        ))

        # Run agent
        updated_state = await self.agent.run(state)
        
        # Verify file content
        md_path = Path(updated_state.completed_md_sections[0])
        content = md_path.read_text(encoding="utf-8")
        
        self.assertIn('"reuse_score": 95', content)
        self.assertIn('"reason": "Perfectly matches the required anatomical view."', content)
        self.assertIn(':::visual', content)
        # Ensure NO <img> tags are present (as per deprecation)
        self.assertNotIn('<img', content)

if __name__ == "__main__":
    unittest.main()
