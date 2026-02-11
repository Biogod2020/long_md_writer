"ImageDownloader: Shotgun Concurrency with Atomic Cleanup."

import requests
import random
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Optional
import urllib3
import json
import shutil
from .browser import BrowserManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImageDownloader:
    """Downloads images using massive parallelism and multi-strategy competition."""

    def __init__(self, browser_manager: BrowserManager, debug: bool = False):
        self.browser_manager = browser_manager
        self.debug = debug

    def download_candidates(self, candidates: List[Dict[str, str]], target_dir: Path) -> List[Path]:
        """
        Shotgun Strategy: Fire ALL methods for ALL images at once.
        Automatically cleans up competing temp files, leaving only the winners.
        """
        if not candidates:
            return []

        if self.debug:
            print(f"    - [Shotgun] Launching extreme parallel download for {len(candidates)} images...")

        max_workers = min(len(candidates) * 4, 100)
        results_map = {} 
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {}
            for i, cand in enumerate(candidates):
                url = cand['url']
                future_to_task[executor.submit(self._method_direct_requests, url, i, target_dir)] = (i, "direct")
                future_to_task[executor.submit(self._method_browser_suite, url, i, target_dir)] = (i, "browser_suite")

            for future in concurrent.futures.as_completed(future_to_task):
                idx, method_name = future_to_task[future]
                try:
                    paths = future.result()
                    if paths:
                        if isinstance(paths, Path): paths = [paths]
                        if idx not in results_map: results_map[idx] = []
                        results_map[idx].extend(paths)
                except Exception: pass

        final_paths = []
        for idx, potential_paths in results_map.items():
            valid_files = [p for p in potential_paths if p.exists() and self._is_valid_image(p)]
            if not valid_files: continue
                
            # Selection: The largest file is usually the highest resolution
            winner = max(valid_files, key=lambda p: p.stat().st_size)
            
            # Standardize filename
            final_path = target_dir / f"img_{idx+1}{winner.suffix}"
            if winner != final_path:
                shutil.copy2(winner, final_path)
            
            # ATOMIC CLEANUP: Delete all competing temp files for THIS image index
            for p in potential_paths:
                try:
                    if p.exists() and p != final_path:
                        p.unlink()
                except: pass
            
            # Secondary sweep for glob pattern safety
            for p in target_dir.glob(f"temp_{idx}_*"):
                try: p.unlink()
                except: pass

            desc = candidates[idx].get('desc')
            if desc: (target_dir / f"img_{idx+1}.txt").write_text(desc, encoding='utf-8')
            final_paths.append(final_path)
                    
        return final_paths

    def _method_direct_requests(self, url: str, index: int, target_dir: Path) -> Optional[Path]:
        try:
            if r'\u' in url: url = url.encode().decode('unicode_escape')
            from urllib.parse import unquote, urlparse
            url = unquote(url)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Referer': f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
            }
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200 and len(resp.content) > 2000:
                c_type = resp.headers.get('Content-Type', '').lower()
                ext = ".png" if 'png' in c_type else ".webp" if 'webp' in c_type else ".jpg"
                p = target_dir / f"temp_{index}_direct{ext}"
                p.write_bytes(resp.content)
                return p
        except: pass
        return None

    def _method_browser_suite(self, url: str, index: int, target_dir: Path) -> List[Path]:
        found = []
        page = self.browser_manager.page
        with ThreadPoolExecutor(max_workers=3) as sub_executor:
            tab = page.new_tab()
            try:
                tab.get(url, timeout=10)
                ua, cookies = tab.user_agent, {c['name']: c['value'] for c in tab.cookies() if isinstance(c, dict)}
                
                def run_fast():
                    try:
                        s = requests.Session()
                        s.headers.update({"User-Agent": ua, "Referer": url})
                        s.cookies.update(cookies)
                        r = s.get(url, timeout=15, verify=False)
                        if r.status_code == 200:
                            p = (target_dir / f"temp_{index}_fast").with_suffix(".png" if 'png' in r.headers.get('Content-Type','') else ".jpg")
                            p.write_bytes(r.content)
                            return p
                    except: return None

                def run_slow():
                    try:
                        res = tab.download(url, str(target_dir.resolve()), f"temp_{index}_slow")
                        return Path(res[1]) if res and res[0] else None
                    except: return None

                futures = [sub_executor.submit(run_fast), sub_executor.submit(run_slow)]
                for f in concurrent.futures.as_completed(futures):
                    res_p = f.result()
                    if res_p: found.append(res_p)
            finally:
                try: tab.close()
                except: pass
        return found

    def _is_valid_image(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.stat().st_size < 2048: return False
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
                return any(header.startswith(m) for m in [b'\xff\xd8\xff', b'\x89PNG', b'RIFF', b'GIF87a', b'GIF89a'])
        except: return False
