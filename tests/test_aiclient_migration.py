import asyncio
import unittest
from src.core.gemini_client import GeminiClient

class TestGeminiClientMigration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # The default URL should now be http://localhost:8888
        self.client = GeminiClient(model="gemini-3-flash-preview")

    async def test_unary_connection(self):
        print("\n🧪 Testing Unary connection to 8888...")
        response = await self.client.generate_async(prompt="Respond with 'MIGRATION_OK'")
        self.assertTrue(response.success, f"Unary failed: {response.error}")
        self.assertIn("MIGRATION_OK", response.text)
        print(f"✅ Unary response received: {response.text[:20]}...")

    async def test_stream_connection(self):
        print("\n🧪 Testing Stream connection to 8888...")
        response = await self.client.generate_async(prompt="Count from 1 to 3", stream=True)
        self.assertTrue(response.success, f"Stream failed: {response.error}")
        self.assertTrue(len(response.text) > 0)
        print(f"✅ Stream content gathered: {response.text[:20]}...")

    async def test_thinking_high(self):
        print("\n🧪 Testing Thinking HIGH on 8888...")
        # gemini-3 series should work fine with thinking on 8888
        response = await self.client.generate_async(
            prompt="Explain the core principle of Einthoven triangle in 1 sentence.",
            thinking_level="HIGH"
        )
        self.assertTrue(response.success, f"Thinking HIGH failed: {response.error}")
        self.assertTrue(len(response.thoughts) > 0)
        print(f"✅ Thoughts captured (len: {len(response.thoughts)})")

if __name__ == "__main__":
    unittest.main()
