import unittest
import os
from pathlib import Path
from src.agents.editorial_qa_agent import EditorialQAAgent
from src.agents.visual_qa.renderer import PlaywrightRenderer
from src.core.types import AgentState
from src.core.gemini_client import GeminiClient

# Check if API key is present
SKIP_REAL_API = os.getenv("GOOGLE_API_KEY") is None

class TestEditorialRealE2E(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if SKIP_REAL_API:
            self.skipTest("GOOGLE_API_KEY not found in environment.")
            
        self.test_dir = Path("test_output/real_e2e")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        (self.test_dir / "assets").mkdir(exist_ok=True)
        
        # Create a real red square image in assets/
        self.image_path = self.test_dir / "assets" / "red_square.png"
        self._create_red_square(self.image_path)
        
        self.renderer = PlaywrightRenderer(self.test_dir, headless=True)
        self.client = GeminiClient() # Real Client
        self.agent = EditorialQAAgent(client=self.client, renderer=self.renderer, max_iterations=1)

    def _create_red_square(self, path: Path):
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(path)

    async def test_real_visual_semantic_fix(self):
        """
        Real E2E Test:
        1. Content claims image is BLUE.
        2. Image is RED.
        3. Agent should detect mismatch and fix text to say RED.
        """
        # Ensure absolute path for renderer to find it
        abs_img_path = self.image_path.absolute()
        
        # Markdown content with semantic error (claims Blue, is Red)
        content = f"""
# Test Section

Here is a shape.
<img src="{abs_img_path}" alt="A square shape">

The color of this square is **BLUE**.
"""
        state = AgentState(job_id="real_e2e_job", workspace_path=str(self.test_dir))
        namespace = "real_e2e"
        
        print("\n[Test] Starting Real E2E Run...")
        
        # We need to make sure the VLM actually sees it as Red.
        # "full_context" helps set the standard.
        
        new_state, report, final_content = await self.agent.run_async(
            state, 
            content, 
            namespace, 
            full_context="Context: We are analyzing colored shapes. Accuracy is paramount."
        )
        
        print(f"\n[Test] Report Passed: {report.passed}")
        print(f"[Test] Issues Found: {len(report.issues)}")
        for i in report.issues:
            print(f"  - {i.issue_type}: {i.message}")
            
        print(f"\n[Test] Final Content:\n{final_content}")

        # Assertions
        # 1. It should have found at least one issue (Semantic Drift or Mismatch)
        self.assertTrue(len(report.issues) > 0, "Expected agent to find the color mismatch.")
        
        # 2. It should have fixed it
        self.assertIn("RED", final_content.upper())
        self.assertNotIn("BLUE", final_content.upper())

if __name__ == "__main__":
    unittest.main()
