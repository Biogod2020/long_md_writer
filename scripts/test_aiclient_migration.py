"""
Smoke test for AIClient-2-API migration.
Attempts to connect to http://localhost:3000 using GeminiClient.
Expected to FAIL initially until GeminiClient is updated.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.gemini_client import GeminiClient

async def test_aiclient_migration():
    print("🚀 [TEST] AIClient-2-API Migration Smoke Test")
    
    # Use DEFAULT configuration (currently 8888)
    client = GeminiClient()
    
    print(f"📡 Target URL (Default): {client.api_base_url}")
    print(f"📦 Model: {client.model}")
    
    try:
        # Simple health check prompt
        print("⏳ Sending test generation request...")
        resp = await client.generate_async(
            prompt="Hello AIClient-2-API, please confirm your connectivity. Respond with 'ACK'.",
            temperature=0.1
        )
        
        if resp.success:
            print(f"✅ [SUCCESS] AIClient-2-API responded: {resp.text.strip()}")
            if "ACK" in resp.text.upper():
                print("🏆 CONNECTION VERIFIED.")
                return True
            else:
                print("⚠️  [WARNING] Unexpected response content.")
                return False
        else:
            print(f"❌ [FAILURE] AIClient-2-API error: {resp.error}")
            return False
            
    except Exception as e:
        print(f"💥 [CRASH] Smoke test exception: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_aiclient_migration())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
