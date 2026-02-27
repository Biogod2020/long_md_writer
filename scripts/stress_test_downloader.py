import asyncio
import time
from pathlib import Path
from src.agents.image_sourcing.browser import BrowserManager
from src.agents.image_sourcing.downloader import ImageDownloader

async def run_stress_test():
    print("🚀 Starting ImageDownloader Stress Test...")
    
    # Create a temporary directory for downloads
    target_dir = Path("workspace/temp_downloader_test")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Extreme Stress Test Mix:
    # 2x Reliable images
    # 5x 403 Forbidden pages (to test semaphore exhaustion)
    # 5x 20-second timeout pages (to test physical tab closure and wait_for interruption)
    # 3x Invalid formats
    # 20 concurrent requests
    candidates = [
        {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/512px-React-icon.svg.png", "desc": "React Logo"},
        {"url": "https://www.google.com/images/branding/googlelogo/1x/googlelogo_color_272x92dp.png", "desc": "Google Logo"},
    ]
    
    # Add 5 HTTP 403s
    for i in range(5):
        candidates.append({"url": "https://httpstat.us/403", "desc": f"Simulated 403 {i}"})
        
    # Add 5 Hanging URLs (20s delay, but our timeout is 15s)
    for i in range(5):
        candidates.append({"url": f"https://httpstat.us/200?sleep=20000&id={i}", "desc": f"Hanging 20s {i}"})
        
    # Add 3 Invalid / 404
    for i in range(3):
        candidates.append({"url": "https://httpstat.us/404", "desc": f"Simulated 404 {i}"})
        
    # Add 5 large random placeholder images to ensure real downloads happen concurrently
    for i in range(5):
        candidates.append({"url": f"https://picsum.photos/1024/768?random={i}", "desc": f"Random Large {i}"})
    
    start_time = time.time()
    
    try:
        with BrowserManager(headless=True, debug=True, block_resources=False) as bm:
            downloader = ImageDownloader(browser_manager=bm, debug=True)
            
            print(f"📦 Submitting {len(candidates)} candidates for parallel download...")
            results = await downloader.download_candidates_async(candidates, target_dir)
            
            print(f"
✅ Download completed in {time.time() - start_time:.2f} seconds.")
            print(f"🎉 Successfully downloaded {len(results)} images:")
            for p in results:
                print(f"  - {p.name} ({p.stat().st_size} bytes)")
                
    except Exception as e:
        print(f"
❌ Test Failed with Exception: {e}")
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(target_dir, ignore_errors=True)
        print("🧹 Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
