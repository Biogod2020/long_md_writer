
import sys
import os
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.core.gemini_client import GeminiClient

async def test_parallel_large():
    api_url = os.getenv("API_URL", "http://localhost:8888/v1")
    client = GeminiClient(api_base_url=api_url, timeout=300)
    
    # 3 Parallel tasks with 200k chars each
    padding = "PING " * 40000 
    tasks = [
        {
            "prompt": f"Task 1: Process this {padding}\nSummary in one word.",
            "issue_id": "T1"
        },
        {
            "prompt": f"Task 2: Process this {padding}\nSummary in one word.",
            "issue_id": "T2"
        },
        {
            "prompt": f"Task 3: Process this {padding}\nSummary in one word.",
            "issue_id": "T3"
        }
    ]
    
    print(f"Starting 3 parallel tasks with ~200k chars each...")
    responses = await client.generate_parallel_async(tasks, debug=True)
    
    for i, resp in enumerate(responses):
        if resp.success:
            print(f"Task {i+1} Success: {resp.text}")
        else:
            print(f"Task {i+1} Failed: {resp.error}")

if __name__ == "__main__":
    asyncio.run(test_parallel_large())
