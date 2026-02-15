import asyncio
import os
import shutil
import time
import hashlib
from pathlib import Path
from src.agents.image_sourcing.agent import ImageSourcingAgent
from src.agents.image_sourcing.browser import BrowserManager
from src.agents.image_sourcing.strategy import StrategyGenerator
from src.agents.image_sourcing.search import GoogleImageSearcher
from src.agents.image_sourcing.downloader import ImageDownloader
from src.agents.image_sourcing.vision import VisionSelector
from src.core.gemini_client import GeminiClient
from src.core.types import AgentState, Manifest, SectionInfo, AssetEntry, AssetSource, AssetVQAStatus

def sync_process_task(client, task, ws_path):
    img_id = task["id"]
    description = task["desc"]
    print(f"\n🚀 [THREAD] Starting Task: {img_id} ({description})")
    
    task_start = time.time()
    
    # 1. 策略生成
    strategy_gen = StrategyGenerator(client)
    strategy = strategy_gen.generate(description, f"A document about {description}")
    queries = strategy.get("queries", [description])[:2]
    print(f"  [{img_id}] Queries: {queries}")

    # 2. 搜索与下载
    all_candidates = []
    with BrowserManager(headless=True, block_resources=True) as bm:
        searcher = GoogleImageSearcher(bm)
        downloader = ImageDownloader(bm)
        
        for q_idx, query in enumerate(queries):
            print(f"  [{img_id}] Searching Query {q_idx+1}: {query}...")
            search_results = searcher.search([query])
            all_candidates.extend(search_results[:20])
        
        seen_urls = set()
        unique_candidates = []
        for c in all_candidates:
            if c['url'] not in seen_urls:
                unique_candidates.append(c)
                seen_urls.add(c['url'])
        
        print(f"  [{img_id}] Unique candidates: {len(unique_candidates)}. Downloading...")
        
        temp_dir = ws_path / f"candidates_{img_id}"
        temp_dir.mkdir(exist_ok=True)
        local_images = downloader.download_candidates(unique_candidates, temp_dir)
        
        # 3. 视觉审计 (TRUE ASYNC inside)
        print(f"  [{img_id}] VLM Audit (Batch 20): Analyzing {len(local_images)} images...")
        vision_selector = VisionSelector(client, debug=True)
        
        descriptions_map = {}
        for img_path in local_images:
            txt_path = img_path.with_suffix('.txt')
            if txt_path.exists():
                descriptions_map[img_path.name] = txt_path.read_text(encoding='utf-8')
        
        guidance = strategy.get("guidance", "Accurate image.")
        
        # 既然我们在线程中，我们还是需要一个事件循环来运行 vision_selector 的异步方法
        async def run_audit():
            return await vision_selector.select_best_async(local_images, description, guidance, descriptions_map)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ranked_winners = loop.run_until_complete(run_audit())
        finally:
            loop.close()

        # 保存详细审计结果供用户查看
        audit_log = ws_path / f"audit_details_{img_id}.json"
        log_data = {
            "intent": description,
            "candidates_count": len(local_images),
            "results": [
                {
                    "path": str(r["path"]), 
                    "reason": r["reason"], 
                    "vlm_description": r["description"],
                    "score": r["score"],
                    "full_metadata": r["metadata"]
                } 
                for r in ranked_winners
            ]
        }
        audit_log.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")
        
        task_duration = time.time() - task_start
        
        if ranked_winners:
            # 取得分最高的那张（如果有多个 batch）
            best_res = max(ranked_winners, key=lambda x: x["score"])
            best_path = best_res["path"]
            final_ext = best_path.suffix
            final_path = ws_path / f"{img_id}{final_ext}"
            shutil.copy2(best_path, final_path)
            print(f"  [{img_id}] ✅ SUCCESS: Found best match (Score: {best_res['score']}) in {task_duration:.2f}s")
            return {"id": img_id, "status": "PASS", "time": task_duration, "score": best_res['score']}
        else:
            print(f"  [{img_id}] ❌ FAIL: No suitable image found in {task_duration:.2f}s")
            return {"id": img_id, "status": "FAIL", "time": task_duration}

async def process_task_wrapper(client, task, ws_path, delay):
    if delay > 0:
        await asyncio.sleep(delay)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_process_task, client, task, ws_path)

async def run_stress_test_v6():
    print("🔥 [STRESS TEST V6] Starting TRUE Staggered Parallel Sourcing (Executor Mode)...")
    
    client = GeminiClient()
    ws_id = f"stress_sourcing_v6_{int(time.time())}"
    ws_path = Path(f"workspaces/workspace/{ws_id}")
    ws_path.mkdir(parents=True, exist_ok=True)
    
    test_tasks = [
        {"id": "gz2hs-logo", "desc": "广州市第二中学的校徽"},
        {"id": "gz2hs-uniform", "desc": "广州市第二中学的校服"},
        {"id": "person-yujintai", "desc": "复旦大学研究员郁金泰的照片"},
        {"id": "fig-transformer", "desc": "Transformer 论文 'Attention Is All You Need' 的 Figure 1 架构图"}
    ]

    start_total = time.time()
    
    # 真正的并发启动
    tasks = []
    for i, task in enumerate(test_tasks):
        tasks.append(process_task_wrapper(client, task, ws_path, delay=i*2))

    print(f"🚀 Launching {len(test_tasks)} threads with 2s intervals...")
    results = await asyncio.gather(*tasks)

    total_duration = time.time() - start_total
    print("\n" + "="*50)
    print(f"📊 TRUE PARALLEL STRESS TEST COMPLETE (Total: {total_duration:.2f}s)")
    for res in results:
        if res:
            print(f"- {res['id']}: {res['status']} ({res['time']:.2f}s)")
    print(f"Artifacts: {ws_path}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_stress_test_v6())
