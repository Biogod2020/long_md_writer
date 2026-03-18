import asyncio
import json
import time
import httpx

async def test_thinking_health(provider_name):
    url = "http://localhost:3000/v1beta/models/gemini-3-flash-preview:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 123456",
        "Model-Provider": provider_name
    }
    payload = {
        "contents": [{"parts": [{"text": "Derive the physical relationship between Wilson Central Terminal and the cardiac dipole. Be extremely detailed."}]}],
        "generationConfig": {
            "thinkingConfig": {
                "includeThoughts": True,
                "thinkingLevel": "HIGH"
            },
            "responseModalities": ["TEXT"]
        }
    }
    
    print(f"📡 Testing Thinking HIGH on: {provider_name} ...")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            elapsed = time.time() - start
            if resp.status_code == 200:
                data = resp.json()
                print(f"  ✅ {provider_name}: HEALTHY ({elapsed:.2f}s)")
                return True
            else:
                print(f"  ❌ {provider_name}: FAILED (HTTP {resp.status_code}) - {resp.text[:150]}...")
                return False
    except Exception as e:
        print(f"  💀 {provider_name}: ERROR - {str(e)}")
        return False

async def run_stress_diagnostics():
    providers = ["gemini-cli-oauth", "gemini-antigravity"]
    print("🚀 Starting API Thinking HIGH Stress Check...")
    
    for p in providers:
        print(f"\n--- Provider Pool: {p} ---")
        for i in range(3): # Hit each pool multiple times to test rotation
            await test_thinking_health(p)
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_stress_diagnostics())
