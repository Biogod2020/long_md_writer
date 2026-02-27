import asyncio
import time
import shutil
from pathlib import Path
from src.agents.image_sourcing.browser import BrowserManager
from src.agents.image_sourcing.search import GoogleImageSearcher
from src.agents.image_sourcing.downloader import ImageDownloader

async def process_term(term, searcher, downloader, test_dir):
    term_dir = test_dir / term.replace(" ", "_")
    term_dir.mkdir(exist_ok=True)
    
    print(f"🔍 [Parallel] Starting search for: {term}")
    # Search is still somewhat serial per term because Google blocks concurrent same-IP searches
    # but the download phase will be fully mixed and parallel.
    candidates = searcher.search([term])
    selected = candidates[:30]
    
    print(f"  - Term '{term}': Found {len(candidates)} candidates. Downloading top {len(selected)}...")
    results = await downloader.download_candidates_async(selected, term_dir)
    return len(results), len(selected)

async def process_term(term, searcher, downloader, test_dir, pbar):
    term_dir = test_dir / term.replace(" ", "_")
    term_dir.mkdir(exist_ok=True)
    
    # 1. Search (Keep sequential per term to be kind to Google)
    candidates = searcher.search([term])
    selected = candidates[:30]
    
    # 2. Download (This will use the internal concurrency of the downloader)
    # The downloader handles 30 concurrent tasks internally and names them img_1..30
    results = await downloader.download_candidates_async(selected, term_dir)
    
    # Update global progress bar by the number of attempts
    pbar.update(len(selected))
    return len(results), len(selected)

async def run_massive_test():
    from tqdm.asyncio import tqdm
    search_terms = [
        "广州市第二中学 校服",
        "郁金泰 复旦大学",
        "mit main building",
        "diffusion architecture"
    ]
    
    target_per_term = 30
    total_expected = len(search_terms) * target_per_term
    
    print(f"🚀 INITIATING MASSIVE PARALLEL DOWNLOAD TEST")
    test_dir = Path("workspace/massive_download_test")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    
    try:
        with BrowserManager(headless=True, debug=False, block_resources=True) as bm:
            searcher = GoogleImageSearcher(bm, debug=False)
            downloader = ImageDownloader(bm, debug=False)
            
            pbar = tqdm(total=total_expected, desc="Total Progress")
            
            # RUN TERMS IN PARALLEL (Up to 4 search terms at once)
            tasks = [process_term(term, searcher, downloader, test_dir, pbar) for term in search_terms]
            summary_results = await asyncio.gather(*tasks)
            
            pbar.close()
            all_captured = sum(r[0] for r in summary_results)
            
            end_time = time.time()
            success_rate = (all_captured / total_expected) * 100
            
            print("\n" + "="*60)
            print("🏁 FINAL REPORT")
            print("="*60)
            print(f"Total Time: {end_time - start_time:.2f} seconds")
            print(f"Total Images Captured: {all_captured} / {total_expected}")
            print(f"Success Rate: {success_rate:.2f}%")
            
            if success_rate >= 80:
                print("🏆 RESULT: PASSED (>= 80%)")
            else:
                print("💀 RESULT: FAILED (< 80%)")
            print("="*60)
                
    except Exception as e:
        print(f"\n❌ TEST CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_massive_test())
