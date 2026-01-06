
import sys
import os
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.gemini_client import GeminiClient

async def test_api():
    api_url = os.getenv("API_URL", "http://localhost:8888/v1")
    print(f"Testing API at: {api_url}")
    
    client = GeminiClient(api_base_url=api_url, timeout=120)
    
    # 2. Test Structured Output
    print("\n--- Testing Structured Output ---")
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "message": {"type": "string"}
        },
        "required": ["status", "message"]
    }
    
    try:
        response = await client.generate_structured_async(
            prompt="Respond in JSON format with status='OK' and message='Structured output is working'.",
            response_schema=schema,
            schema_name="TestResponse",
            temperature=0.0
        )
        if response.success:
            print(f"Success! JSON Data: {response.json_data}")
        else:
            print(f"Failed! Error: {response.error}")
    except Exception as e:
        print(f"Exception during structured generation: {e}")

    # 3. Test Very Large Payload
    print("\n--- Testing Very Large Payload ---")
    # Increase the payload significantly
    large_text = "PING " * 100000 # Roughly 500k characters
    try:
        print(f"Sending payload of size: {len(large_text)} chars")
        response = await client.generate_async(
            prompt=f"Here is a very long text. I just want to know if you can receive it. Answer with 'RECEIVED' followed by the approximate length in KB that I sent. Text: {large_text}",
            temperature=0.0
        )
        if response.success:
            print(f"Success! Response: {response.text}")
        else:
            print(f"Failed! Error: {response.error}")
    except Exception as e:
        print(f"Exception during large payload test: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
