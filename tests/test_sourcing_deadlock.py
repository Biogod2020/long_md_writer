import asyncio
import pytest
import time
from pathlib import Path
from src.agents.image_sourcing.browser import BrowserManager
from src.agents.image_sourcing.downloader import ImageDownloader

@pytest.mark.asyncio
async def test_sourcing_deadlock_simulation():
    """
    Simulates multiple hanging download requests to verify the physical 
    circuit-breaker (tab.close()) works and releases semaphores.
    """
    test_dir = Path("workspace/test_deadlock")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. We use a URL that hangs (httpstat.us/200?sleep=60000)
    # The browser_concurrency is 8.
    # 2. We send 10 hanging requests.
    # 3. We send 1 real request at the end.
    hanging_url = "https://httpstat.us/200?sleep=60000"
    real_url = "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png"
    
    candidates = [{"url": hanging_url, "desc": f"Hang {i}"} for i in range(10)]
    candidates.append({"url": real_url, "desc": "Real Image"})
    
    print(f"\n🔥 Starting Deadlock Simulation Test...")
    print(f"📡 Plan: 10 malicious hangs (15s timeout) followed by 1 real asset.")
    print(f"⏱️  Expected runtime: ~35-45 seconds.")
    
    start_time = time.time()
    
    try:
        with BrowserManager(headless=True, debug=True) as bm:
            downloader = ImageDownloader(bm, debug=True)
            
            # The entire collection of tasks should finish when the real one wins
            # or when all hangs hit their 15s circuit breaker.
            results = await asyncio.wait_for(
                downloader.download_candidates_async(candidates, test_dir),
                timeout=70.0 
            )
            
            elapsed = time.time() - start_time
            print(f"✅ Completed in {elapsed:.2f}s")
            print(f"📊 Results: {len(results)} images successfully captured.")
            
            # Assert that the real image was captured eventually
            found_real = any("googlelogo" in str(p).lower() for p in results)
            assert found_real, "CRITICAL: The real image was LOST or blocked by deadlock."
            
            if elapsed < 60:
                print("🏆 SUCCESS: Physical circuit breaker worked. Deadlock avoided.")
            else:
                print("⚠️ WARNING: Test passed but took too long. Check semaphore recycling.")

    except asyncio.TimeoutError:
        pytest.fail("💀 DEADLOCK DETECTED! The process hung beyond 70s threshold.")
    except Exception as e:
        pytest.fail(f"💥 TEST CRASHED: {e}")
    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    asyncio.run(test_sourcing_deadlock_simulation())
