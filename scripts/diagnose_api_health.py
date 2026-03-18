import asyncio
import json
import time
import httpx

async def check_provider_health(provider_name):
    url = "http://localhost:3000/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 123456",
        "Model-Provider": provider_name
    }
    payload = {
        "contents": [{"parts": [{"text": "Ping. Reply with OK."}]}]
    }
    
    print(f"📡 Testing Provider: {provider_name} ...")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            elapsed = time.time() - start
            if resp.status_code == 200:
                print(f"  ✅ {provider_name}: HEALTHY ({elapsed:.2f}s)")
                return True
            else:
                print(f"  ❌ {provider_name}: FAILED (HTTP {resp.status_code}) - {resp.text[:100]}...")
                return False
    except Exception as e:
        print(f"  💀 {provider_name}: ERROR - {str(e)}")
        return False

async def run_diagnostics():
    providers = ["gemini-cli-oauth", "gemini-antigravity"]
    results = {}
    for p in providers:
        # Run 3 tests per provider to check rotation health
        results[p] = []
        for i in range(3):
            results[p].append(await check_provider_health(p))
            await asyncio.sleep(1)
            
    print("\n========================================")
    print("📊 FINAL HEALTH REPORT (Gemini 2.5 Flash)")
    print("========================================")
    for p, res in results.items():
        health_str = " | ".join(["PASS" if r else "FAIL" for r in res])
        print(f"{p:20}: [{health_str}]")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
