import asyncio
import time
import shutil
from pathlib import Path
from src.agents.image_sourcing.browser import BrowserManager
from src.agents.image_sourcing.downloader import ImageDownloader

async def run_extreme_deadlock_test():
    print("🔥 INITIATING EXTREME DEADLOCK STRESS TEST...")
    print("This test simulates a worst-case scenario where many URLs are malicious 'hang' traps.")
    
    target_dir = Path("workspace/extreme_deadlock_test")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Scenario: 
    # - Browser Semaphore is 5.
    # - We send 25 'Trap' URLs that hang for 60 seconds (exceeding our 15s timeout).
    # - We send 5 'Gold' URLs that are fast and reliable.
    # If the fix works, the 5 semaphore slots will be occupied by traps, then 
    # physically CLOSED after 15s, releasing slots for the next batch.
    # The entire process should complete in roughly (30 total / 5 slots) * 15s = ~90 seconds.
    # If it fails, it will hang for 60s per trap or deadlock entirely.
    
    candidates = []
    
    # 25 Traps (Hanging URLs)
    for i in range(25):
        # httpstat.us is perfect for simulating long-running requests
        candidates.append({
            "url": f"https://httpstat.us/200?sleep=60000&id={i}", 
            "desc": f"Deadlock Trap {i}"
        })
        
    # 5 Gold (Real images)
    gold_urls = [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/512px-React-icon.svg.png",
        "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png",
        "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png",
        "https://www.rust-lang.org/static/images/rust-logo-blk.svg",
        "https://www.sqlite.org/images/sqlite370_banner.gif"
    ]
    for i, url in enumerate(gold_urls):
        candidates.append({"url": url, "desc": f"Gold Asset {i}"})

    start_time = time.time()
    
    try:
        # Mimic the ImageSourcingAgent's context
        with BrowserManager(headless=True, debug=True, block_resources=True) as bm:
            downloader = ImageDownloader(bm, debug=True)
            
            print(f"📡 Dispatching {len(candidates)} download tasks (25 traps, 5 real)...")
            print(f"Expected duration: ~90-120s if timeouts are working correctly.")
            
            # Use download_candidates_async directly to simulate agent load
            results = await downloader.download_candidates_async(candidates, target_dir)
            
            elapsed = time.time() - start_time
            print(f"
🏁 EXTREME TEST FINISHED in {elapsed:.2f}s")
            print(f"📊 Results: {len(results)} assets successfully captured.")
            
            # VALIDATION
            # If it took more than 180s, something is wrong (means traps weren't interrupted at 15s)
            if elapsed < 180 and len(results) > 0:
                print("🏆 SUCCESS: Deadlock avoided. Semaphore recycled via physical tab closure.")
            else:
                print("❌ FAILURE: Process took too long or failed to capture any assets.")
                if elapsed >= 180:
                    print("   Reason: Physical timeout/circuit-breaker likely FAILED.")

    except Exception as e:
        print(f"
❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutil.rmtree(target_dir, ignore_errors=True)
        print("🧹 Cleanup complete.")

if __name__ == "__main__":
    # We increase the log verbosity for this run
    asyncio.run(run_extreme_deadlock_test())
