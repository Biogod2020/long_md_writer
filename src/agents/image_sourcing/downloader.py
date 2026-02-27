"""
ImageDownloader: Shotgun Concurrency with VQA Thumbnail Generation.
SOTA 2.1: Optimized for massive parallelism and first-win race conditions.
"""

import httpx
import asyncio
import random
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
import urllib3
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from .browser import BrowserManager
from PIL import Image
import io
import threading

from ...core.config import DEFAULT_BROWSER_CONCURRENCY, DEFAULT_DOWNLOAD_TIMEOUT

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ImageDownloader:
    """
    Downloads images using massive ASYNC parallelism.
    Maintains ORIGINAL binary while generating VQA thumbnails for speed.
    """

    def __init__(self, browser_manager: BrowserManager, debug: bool = False):
        self.browser_manager = browser_manager
        self.debug = debug
        self.timeout = httpx.Timeout(DEFAULT_DOWNLOAD_TIMEOUT, connect=5.0)
        self.max_concurrency = DEFAULT_BROWSER_CONCURRENCY 
        self.browser_concurrency = DEFAULT_BROWSER_CONCURRENCY 
        self.browser_semaphore = asyncio.Semaphore(self.browser_concurrency)
        # SOTA: Thread lock to protect ChromiumPage instance from CDP race conditions
        self.browser_lock = threading.Lock()
        self.vqa_dim = 1024 # Standard dimension for VLM audit

    async def download_candidates_async(self, candidates: List[Dict[str, str]], target_dir: Path) -> List[Path]:
        """
        1. Competition download.
        2. Pick original winners.
        3. Generate VQA thumbnails.
        Returns: List of Path objects to the ORIGINAL files.
        """
        if not candidates: return []
        
        # Filter out padding (dummy) items if any
        real_candidates = [c for c in candidates if c is not None]
        if not real_candidates: return []
        
        if self.debug: print(f"    - [Downloader] Sourcing {len(real_candidates)} candidates...")

        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def competitive_download(idx: int, cand: Optional[Dict[str, str]]) -> List[Path]:
            if cand is None: return [] # Handle padding
            async with semaphore:
                url = cand['url']
                # SOTA 2.1: First-Win Race Condition. 
                # Don't wait for the browser if httpx already finished.
                tasks = [
                    asyncio.create_task(self._method_direct_httpx(url, idx, target_dir)),
                    asyncio.create_task(self._method_browser_suite_async(url, idx, target_dir))
                ]
                
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                
                # Check results and cancel pending
                flat = []
                for task in done:
                    try:
                        res = task.result()
                        if res:
                            if isinstance(res, list): flat.extend(res)
                            else: flat.append(res)
                    except: pass
                
                # If we have a winner, cancel the other one immediately to free resources
                if flat:
                    for p_task in pending: p_task.cancel()
                else:
                    # If no winner yet, wait for the rest
                    if pending:
                        try:
                            done2, _ = await asyncio.wait(pending, timeout=DEFAULT_DOWNLOAD_TIMEOUT)
                            for task in done2:
                                try:
                                    res = task.result()
                                    if res:
                                        if isinstance(res, list): flat.extend(res)
                                        else: flat.append(res)
                                except: pass
                        except asyncio.TimeoutError:
                            for p_task in pending: p_task.cancel()
                
                return flat

        # We must maintain the original indexing for naming (img_1, img_2...)
        # candidates might have None values for padding if called from specialized scripts
        all_results = await asyncio.gather(*[competitive_download(i, c) for i, c in enumerate(candidates)])
        
        original_winners = []
        for idx, potential_paths in enumerate(all_results):
            if idx >= len(candidates) or candidates[idx] is None: continue
            
            valid_files = [p for p in potential_paths if p.exists() and self._is_valid_image(p)]
            if not valid_files: continue
                
            winner = max(valid_files, key=lambda p: p.stat().st_size)
            final_orig_path = target_dir / f"img_{idx+1}{winner.suffix}"
            if winner.absolute() != final_orig_path.absolute():
                shutil.copy2(winner, final_orig_path)
            
            # Generate VQA Thumbnail (Cached once on disk)
            vqa_path = target_dir / f"img_{idx+1}_vqa.jpg"
            await asyncio.to_thread(self._create_vqa_thumb, final_orig_path, vqa_path)

            # SOTA: Aggressive cleanup of temp fragments
            for p in potential_paths:
                try:
                    if p.exists() and p.absolute() != final_orig_path.absolute() and p.absolute() != vqa_path.absolute(): 
                        p.unlink()
                except: pass
            
            # Clean up ANY residual temp files in the target directory for this index
            for p in target_dir.glob(f"temp_{idx}_*"):
                try: 
                    if p.exists() and p.absolute() != final_orig_path.absolute() and p.absolute() != vqa_path.absolute():
                        p.unlink()
                except: pass

            desc = candidates[idx].get('desc')
            if desc: (target_dir / f"img_{idx+1}.txt").write_text(desc, encoding='utf-8')
            original_winners.append(final_orig_path)
                    
        return original_winners

    def _create_vqa_thumb(self, src: Path, dest: Path):
        """Creates a resized JPEG for VLM audit. Source remains untouched."""
        try:
            with Image.open(src) as img:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                
                if max(img.size) > self.vqa_dim:
                    img.thumbnail((self.vqa_dim, self.vqa_dim), Image.Resampling.LANCZOS)
                img.save(dest, "JPEG", quality=85, optimize=True)
        except: pass

    async def _method_direct_httpx(self, url: str, index: int, target_dir: Path) -> Optional[Path]:
        try:
            if r'\u' in url: url = url.encode().decode('unicode_escape')
            from urllib.parse import unquote, urlparse
            domain = urlparse(unquote(url)).netloc
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Referer': f"https://{domain}/"
            }
            # SOTA: Disable proxy for local health but environment proxy usually fine for web
            async with httpx.AsyncClient(verify=False, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 2000:
                    ext = ".png" if 'png' in resp.headers.get('Content-Type', '').lower() else ".webp" if 'webp' in resp.headers.get('Content-Type', '').lower() else ".jpg"
                    p = target_dir / f"temp_{index}_direct{ext}"
                    p.write_bytes(resp.content)
                    return p
        except: pass
        return None

    async def _method_browser_suite_async(self, url: str, index: int, target_dir: Path) -> List[Path]:
        async with self.browser_semaphore:
            tab = None
            try:
                with self.browser_lock:
                    page = self.browser_manager.page
                    tab = page.new_tab()
                    tab.retry_times = 0
                
                # SOTA: Brief sleep to stagger WebSocket handshakes
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
                # 1. Navigation & Data Capture logic
                async def _sync_browser_navigation():
                    try:
                        tab.get(url, timeout=5)
                        ua, cookies = tab.user_agent, {c['name']: c['value'] for c in tab.cookies() if isinstance(c, dict)}
                        
                        # TRI-MODE COMPETITION
                        # A: JS-Binary-Extractor
                        async def _mode_js_fetch():
                            js_code = """
                            async (img_url) => {
                                try {
                                    const resp = await fetch(img_url, {mode: 'no-cors'});
                                    const blob = await resp.blob();
                                    return new Promise((resolve) => {
                                        const reader = new FileReader();
                                        reader.onloadend = () => resolve(reader.result);
                                        reader.readAsDataURL(blob);
                                    });
                                } catch (e) { return null; }
                            }
                            """
                            try:
                                b64_data = tab.run_js(js_code, url)
                                if b64_data and 'base64,' in b64_data:
                                    import base64
                                    header, encoded = b64_data.split(",", 1)
                                    ext = ".png" if "png" in header else ".jpg"
                                    p = target_dir / f"temp_{index}_js{ext}"
                                    p.write_bytes(base64.b64decode(encoded))
                                    return p
                            except: pass
                            return None

                        # B: Mirrored HTTPX (Dynamic Referer)
                        async def _mode_mirrored_httpx():
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(url).netloc
                                headers = {
                                    'User-Agent': ua, 
                                    'Referer': f"https://{domain}/",
                                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                                }
                                async with httpx.AsyncClient(verify=False, timeout=10.0, cookies=cookies, follow_redirects=True) as client:
                                    resp = await client.get(url, headers=headers)
                                    if resp.status_code == 200 and len(resp.content) > 2000:
                                        ext = ".png" if 'png' in resp.headers.get('Content-Type', '').lower() else ".jpg"
                                        p = target_dir / f"temp_{index}_mir{ext}"
                                        p.write_bytes(resp.content)
                                        return p
                            except: pass
                            return None

                        # C: Native Mission
                        async def _mode_mission_fallback():
                            try:
                                abs_target = str(target_dir.resolve())
                                tab.set.download_path(abs_target)
                                mission = tab.download.add(url, f"temp_{index}_ms")
                                start_wait = time.time()
                                while time.time() - start_wait < 10:
                                    if mission.state == 'done': return Path(mission.file_path)
                                    if mission.state in ['failed', 'cancelled']: break
                                    await asyncio.sleep(0.5)
                                mission.cancel()
                            except: pass
                            return None

                        # Sub-race within browser session
                        results = await asyncio.gather(_mode_js_fetch(), _mode_mirrored_httpx(), _mode_mission_fallback())
                        return [p for p in results if p and p.exists() and p.stat().st_size > 2000]
                    except: return []

                # Wrap the browser session in a thread with a hard global timeout
                result = await asyncio.wait_for(
                    _sync_browser_navigation(), 
                    timeout=12.0
                )
                return result if result else []

            except (asyncio.TimeoutError, Exception):
                return []
            finally:
                if tab:
                    try: tab.close()
                    except: pass

    def _is_valid_image(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.stat().st_size < 2048: return False
        try:
            with Image.open(file_path) as img:
                img = img.convert("RGB")
                img.verify()
            return True
        except: return False

    def download_candidates(self, candidates: List[Dict[str, str]], target_dir: Path) -> List[Path]:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with ThreadPoolExecutor() as executor:
                    return executor.submit(lambda: asyncio.run(self.download_candidates_async(candidates, target_dir))).result()
            return asyncio.run(self.download_candidates_async(candidates, target_dir))
        except RuntimeError: return asyncio.run(self.download_candidates_async(candidates, target_dir))
