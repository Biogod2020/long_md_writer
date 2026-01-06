
import sys
import os
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.gemini_client import GeminiClient

async def test_truncation():
    api_url = os.getenv("API_URL", "http://localhost:8888/v1")
    client = GeminiClient(api_base_url=api_url, timeout=120)
    
    magic_suffix = "END_OF_PROMPT_MAGIC_12345"
    # Create 300k chars payload
    padding = "PADDING " * 40000 # ~320k chars
    full_prompt = f"Please repeat the text after 'MAGIC:' exactly. MAGIC: {magic_suffix}\nExclude everything before 'MAGIC:'.\n\nContent: {padding}"
    
    print(f"Sending prompt of size: {len(full_prompt)} chars")
    
    try:
        response = await client.generate_async(
            prompt=full_prompt,
            temperature=0.0
        )
        if response.success:
            print(f"Response: {response.text}")
            if magic_suffix in response.text:
                print("Magic suffix found! Full prompt received by model.")
            else:
                print("Magic suffix NOT found! Prompt likely truncated.")
        else:
            print(f"Failed! Error: {response.error}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_truncation())
