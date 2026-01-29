import unittest
import sys
from pathlib import Path
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.gemini_client import GeminiClient, GeminiResponse

class TestNativeGeminiClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = GeminiClient(api_base_url="http://test-proxy", auth_token="test-token")

    def test_build_native_contents_simple(self):
        """Test building simple text contents."""
        prompt = "Hello"
        contents = self.client._build_native_contents(prompt, None)
        
        expected = [{"role": "user", "parts": [{"text": "Hello"}]}]
        self.assertEqual(contents, expected)

    def test_build_native_contents_multimodal(self):
        """Test building multimodal contents with inline_data."""
        prompt = "Analyze this image"
        parts = [
            {"inline_data": {"mime_type": "image/jpeg", "data": "BASE64BYTES"}}
        ]
        contents = self.client._build_native_contents(prompt, parts)
        
        expected = [{
            "role": "user",
            "parts": [
                {"text": "Analyze this image"},
                {"inline_data": {"mime_type": "image/jpeg", "data": "BASE64BYTES"}}
            ]
        }]
        self.assertEqual(contents, expected)

    def test_parse_native_response_with_thoughts(self):
        """Test parsing a native response that includes thinking tokens."""
        mock_data = {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [
                        {"thought": True, "text": "I should say hello."}, 
                        {"text": "Hello there!"}
                    ]
                },
                "finishReason": "STOP"
            }]
        }
        
        response = self.client._parse_native_response(mock_data)
        
        self.assertTrue(response.success)
        self.assertEqual(response.text, "Hello there!")
        self.assertEqual(response.thoughts, "I should say hello.")

    def test_parse_native_response_json(self):
        """Test parsing a native response containing JSON."""
        mock_data = {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{"text": '```json\n{"key": "value"}\n```'}]
                }
            }]
        }
        
        response = self.client._parse_native_response(mock_data)
        
        self.assertTrue(response.success)
        self.assertEqual(response.json_data, {"key": "value"})

    @patch("httpx.AsyncClient.post")
    async def test_generate_async_native_endpoint(self, mock_post):
        """Test that generate_async calls the correct native endpoint."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
        
        await self.client.generate_async(prompt="Hi")
        
        # Verify URL (v1beta/models/...)
        call_url = mock_post.call_args[0][0]
        self.assertIn("/v1beta/models/", call_url)
        self.assertIn(":generateContent", call_url)

if __name__ == "__main__":
    unittest.main()
