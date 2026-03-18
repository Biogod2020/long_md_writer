import asyncio
import json
import time
import httpx

async def test_thinking_extreme(provider_name, task_name, prompt):
    url = "http://localhost:3000/v1beta/models/gemini-3-flash-preview:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 123456",
        "Model-Provider": provider_name
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "thinkingConfig": {
                "includeThoughts": True,
                "thinkingLevel": "HIGH"
            },
            "responseModalities": ["TEXT"]
        }
    }
    
    print(f"🔥 [EXTREME TEST] Task: {task_name} | Provider: {provider_name} ...")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            elapsed = time.time() - start
            if resp.status_code == 200:
                data = resp.json()
                print(f"  ✅ SUCCESS ({elapsed:.2f}s)")
                # Print a snippet of thoughts to prove depth
                for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if part.get("thought"):
                        print(f"     [Thought Snippet]: {part.get('text', '')[:150]}...")
                return True
            else:
                print(f"  ❌ FAILED (HTTP {resp.status_code}) - {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"  💀 ERROR: {str(e)}")
        return False

async def run_pressure_suite():
    tasks = [
        ("Physics", "Derive the Schwarzschild metric from the Einstein field equations in vacuum. Explain the physical significance of the event horizon and the singularity."),
        ("Quantum", "Propose a new logical qubit encoding scheme that specifically mitigates non-Markovian noise in a topological lattice. Provide mathematical justifications."),
        ("Engineering", "Analyze the non-linear shift of the Wilson Central Terminal (WCT) during acute transmural myocardial ischemia from a volume conductor perspective. How do boundary conditions change when local conductivity sigma drops?")
    ]
    
    # We will alternate providers to test the pool
    providers = ["gemini-cli-oauth", "gemini-antigravity"]
    
    print("\n🚀 INITIATING SOTA THINKING-HIGH PRESSURE SUITE\n")
    
    for i, (name, prompt) in enumerate(tasks):
        p = providers[i % len(providers)]
        await test_thinking_extreme(p, name, prompt)
        await asyncio.sleep(2) # Brief gap

if __name__ == "__main__":
    asyncio.run(run_pressure_suite())
