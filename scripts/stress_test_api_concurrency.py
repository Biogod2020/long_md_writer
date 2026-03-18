import asyncio
import time
import random
from src.core.gemini_client import GeminiClient

async def single_worker(client, task_id):
    prompt = f"Task {task_id}: Explain the concept of electromagnetic induction in one sentence."
    # We use thinking_level=None for faster testing of pure concurrency
    start = time.time()
    resp = await client.generate_async(prompt=prompt, temperature=0.1)
    elapsed = time.time() - start
    
    if resp.success:
        print(f"✅ [Worker {task_id}] Success in {elapsed:.2f}s")
        return True
    else:
        print(f"❌ [Worker {task_id}] FAILED: {resp.error}")
        return False

async def run_pressure_test(concurrency=15):
    print(f"🔥 INITIATING API PRESSURE TEST (Concurrency: {concurrency})")
    
    client = GeminiClient()
    start_time = time.time()
    
    # Launch all workers concurrently
    tasks = [single_worker(client, i) for i in range(concurrency)]
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    success_count = sum(1 for r in results if r)
    
    print("\n========================================")
    print("📊 CONCURRENCY TEST REPORT")
    print("========================================")
    print(f"Total Tasks    : {concurrency}")
    print(f"Successes      : {success_count}")
    print(f"Failures       : {concurrency - success_count}")
    print(f"Success Rate   : {(success_count/concurrency)*100:.2f}%")
    print(f"Total Duration : {total_time:.2f}s")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(run_pressure_test())
