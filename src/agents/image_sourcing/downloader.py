"ImageDownloader: Shotgun Concurrency with VQA Thumbnail Generation."

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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImageDownloader:
    """
    Downloads images using massive ASYNC parallelism.
    Maintains ORIGINAL binary while generating VQA thumbnails for speed.
    """

    def __init__(self, browser_manager: BrowserManager, debug: bool = False):
        self.browser_manager = browser_manager
        self.debug = debug
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        self.max_concurrency = 30 
        self.browser_concurrency = 5 # SOTA: 限制浏览器标签页数量
        self.browser_semaphore = asyncio.Semaphore(self.browser_concurrency)
        self.vqa_dim = 1024 # Standard dimension for VLM audit

    async def download_candidates_async(self, candidates: List[Dict[str, str]], target_dir: Path) -> List[Path]:
        """
        1. Competition download.
        2. Pick original winners.
        3. Generate VQA thumbnails.
        Returns: List of Path objects to the ORIGINAL files.
        """
        if not candidates: return []
        if self.debug: print(f"    - [Downloader] Sourcing {len(candidates)} candidates...")

        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def competitive_download(idx: int, cand: Dict[str, str]) -> List[Path]:
            async with semaphore:
                url = cand['url']
                tasks = [
                    self._method_direct_httpx(url, idx, target_dir),
                    self._method_browser_suite_async(url, idx, target_dir)
                ]
                results = await asyncio.gather(*tasks)
                flat = []
                for r in results:
                    if isinstance(r, list): flat.extend(r)
                    elif isinstance(r, Path): flat.append(r)
                return flat

        all_results = await asyncio.gather(*[competitive_download(i, c) for i, c in enumerate(candidates)])
        
        original_winners = []
        for idx, potential_paths in enumerate(all_results):
            valid_files = [p for p in potential_paths if p.exists() and self._is_valid_image(p)]
            if not valid_files: continue
                
            winner = max(valid_files, key=lambda p: p.stat().st_size)
            final_orig_path = target_dir / f"img_{idx+1}{winner.suffix}"
            if winner != final_orig_path: shutil.copy2(winner, final_orig_path)
            
            # Generate VQA Thumbnail (Cached once on disk)
            vqa_path = target_dir / f"img_{idx+1}_vqa.jpg"
            await asyncio.to_thread(self._create_vqa_thumb, final_orig_path, vqa_path)

            # Cleanup fragments
            for p in potential_paths:
                try:
                    if p.exists() and p != final_orig_path and p != vqa_path: p.unlink()
                except: pass
            for p in target_dir.glob(f"temp_{idx}_*"):
                try: p.unlink()
                except: pass

            desc = candidates[idx].get('desc')
            if desc: (target_dir / f"img_{idx+1}.txt").write_text(desc, encoding='utf-8')
            original_winners.append(final_orig_path)
                    
        return original_winners

    def _create_vqa_thumb(self, src: Path, dest: Path):
        """Creates a resized JPEG for VLM audit. Source remains untouched."""
        try:
            with Image.open(src) as img:
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                if max(img.size) > self.vqa_dim:
                    img.thumbnail((self.vqa_dim, self.vqa_dim), Image.Resampling.LANCZOS)
                img.save(dest, "JPEG", quality=85, optimize=True)
        except: pass

    async def _method_direct_httpx(self, url: str, index: int, target_dir: Path) -> Optional[Path]:
        try:
            if r'\u' in url: url = url.encode().decode('unicode_escape')
            from urllib.parse import unquote, urlparse
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Referer': f"{urlparse(unquote(url)).scheme}://{urlparse(unquote(url)).netloc}/"
            }
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
            def sync_browser_work():
                found = []
                try:
                    page = self.browser_manager.page
                    tab = page.new_tab()
                except Exception as e:
                    if self.debug: print(f"      [Browser] Failed to open tab: {e}")
                    return []
                
                try:
                    tab.get(url, timeout=10)
                    ua, cookies = tab.user_agent, {c['name']: c['value'] for c in tab.cookies() if isinstance(c, dict)}
                    try:
                        import requests
                        s = requests.Session()
                        s.headers.update({"User-Agent": ua, "Referer": url})
                        s.cookies.update(cookies)
                        r = s.get(url, timeout=10, verify=False)
                        if r.status_code == 200:
                            p = (target_dir / f"temp_{index}_fast").with_suffix(".png" if 'png' in r.headers.get('Content-Type','') else ".jpg")
                            p.write_bytes(r.content)
                            found.append(p)
                    except: pass
                    try:
                        res = tab.download(url, str(target_dir.resolve()), f"temp_{index}_slow")
                        if res and res[0]: found.append(Path(res[1]))
                    except: pass
                except Exception as e:
                    if self.debug: print(f"      [Browser] Error during tab session: {e}")
                finally:
                    try: tab.close()
                    except: pass
                return found
            return await asyncio.to_thread(sync_browser_work)

    def _is_valid_image(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.stat().st_size < 2048: return False
        try:
            with Image.open(file_path) as img: img.verify()
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
