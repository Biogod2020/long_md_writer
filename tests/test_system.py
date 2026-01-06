
import sys
import os
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.gemini_client import GeminiClient

async def test_system_instruction():
    api_url = os.getenv("API_URL", "http://localhost:8888/v1")
    client = GeminiClient(api_base_url=api_url, timeout=60)
    
    print("\n--- Testing with System Instruction ---")
    try:
        response = await client.generate_async(
            prompt="Who are you?",
            system_instruction="You are a robot named BEEP-BOOP-42.",
            temperature=0.0
        )
        if response.success:
            print(f"Success! Response: {response.text}")
        else:
            print(f"Failed! Error: {response.error}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_system_instruction())
