"ImageDownloader: Robust multi-layer download strategy for image candidates."

import requests
import random
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Optional
import urllib3
import json
from .browser import BrowserManager

# Disable insecure request warnings for proxy/SSL issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ImageDownloader:
    """Downloads images using requests with browser fallback."""

    def __init__(self, browser_manager: BrowserManager, debug: bool = False):
        self.browser_manager = browser_manager
        self.debug = debug

    def download_candidates(self, candidates: List[Dict[str, str]], target_dir: Path) -> List[Path]:
        """
        Download a list of candidate images using a 3-layer strategy.
        
        Args:
            candidates: List of {'url', 'desc'} dicts
            target_dir: Directory to save images
            
        Returns:
            List of Path objects for successfully downloaded images
        """
        if not candidates:
            return []
            
        session = requests.Session()
        local_paths = [None] * len(candidates)
        failed_indices = []

        # 1. LAYER 1: Parallel Requests
        if self.debug:
            print(f"    - Starting parallel download of {len(candidates)} images...")
            
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    self._download_single_requests, 
                    candidates[i]['url'], 
                    i, 
                    target_dir, 
                    session, 
                    candidates[i]['desc']
                ): i for i in range(len(candidates))
            }
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    path = future.result()
                    if path:
                        local_paths[idx] = path
                    else:
                        failed_indices.append(idx)
                except:
                    failed_indices.append(idx)

        # 2. LAYER 2: Browser Fallback (Anti-bot Bypass + Session Injection)
        if failed_indices:
            if self.debug:
                print(f"    - {len(failed_indices)} failed simple download. Trying Browser-based fallback...")
            
            # Use the shared browser instance
            page = self.browser_manager.page

            try:
                downloader_tab = page.new_tab()
                for i in failed_indices:
                    url = candidates[i]['url']
                    desc = candidates[i]['desc']
                    try:
                        if self.debug:
                            print(f"      - Fallback trying {i+1} via Browser...")
                        
                        # A. Navigate to bypass checks (Cloudflare/hotlink protection)
                        downloader_tab.get(url, timeout=12)
                        
                        # Wait briefly for challenges
                        if "cloudflare" in downloader_tab.title.lower() or "just a moment" in downloader_tab.title.lower():
                            if self.debug: print("        [!] Anti-bot challenge detected, waiting...")
                            time.sleep(3)
                            downloader_tab.wait.doc_loaded(timeout=5)

                        # B. INJECT COOKIES into a fast requests Session
                        try:
                            # Use dict format for easier session update
                            raw_cookies = {}
                            try:
                                c_list = downloader_tab.cookies()
                                for c in c_list:
                                    if isinstance(c, dict):
                                        raw_cookies[c.get('name')] = c.get('value')
                            except:
                                pass
                        except:
                            raw_cookies = {}
                        
                        ua = downloader_tab.user_agent
                        from urllib.parse import urlparse
                        parsed_url = urlparse(url)
                        domain_referer = f"{parsed_url.scheme}://{parsed_url.netloc}/"
                        
                        # Create high-fidelity requests session
                        fast_session = requests.Session()
                        fast_session.headers.update({
                            "User-Agent": ua, 
                            "Referer": domain_referer,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                            "Accept-Language": "en-US,en;q=0.9",
                            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Bar";v="24", "Google Chrome";v="122"',
                            "Sec-Ch-Ua-Mobile": "?0",
                            "Sec-Ch-Ua-Platform": '"macOS"',
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                            "Upgrade-Insecure-Requests": "1"
                        })
                        fast_session.cookies.update(raw_cookies)
                        
                        # C. Fast Download
                        target_path = target_dir / f"img_{i+1}"
                        download_success = False
                        
                        try:
                            # Stream download
                            resp = fast_session.get(url, stream=True, timeout=25, verify=False)
                            
                            # SOTA: If 403 or 567, try one last time with stripped headers
                            if resp.status_code in [403, 567]:
                                if self.debug: print(f"        [!] Status {resp.status_code} detected, trying Clean Header Fallback...")
                                clean_headers = {
                                    'User-Agent': ua,
                                    'Accept': 'image/*',
                                    'Referer': domain_referer
                                }
                                resp = session.get(url, headers=clean_headers, timeout=30, verify=False, stream=True)

                            if resp.status_code == 200:
                                c_type = resp.headers.get('Content-Type', '').lower()
                                ext = ".png" if 'png' in c_type else ".webp" if 'webp' in c_type else ".jpg"
                                final_path = target_path.with_suffix(ext)
                                
                                with open(final_path, 'wb') as f:
                                    for chunk in resp.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                        
                                self._resize_image(final_path)
                                if self._is_valid_image(final_path):
                                    downloaded_path = final_path
                                    if self.debug: print(f"        [+] Fast session download success: {downloaded_path.name}")
                                    if desc: (target_dir / f"{downloaded_path.stem}.txt").write_text(desc, encoding='utf-8')
                                    local_paths[i] = downloaded_path
                                    download_success = True
                                else:
                                    if self.debug: print("        [-] Fast session integrity check failed.")
                                    if final_path.exists(): final_path.unlink()
                            else:
                                if self.debug: print(f"        [-] Fast session download failed: {resp.status_code}")
                        except Exception as e:
                            if self.debug: print(f"        [-] Fast session error: {e}")

                        # D. Slow Browser Download (Last Resort)
                        if not download_success:
                            if self.debug: print(f"        [!] Reverting to slow browser download for {i+1}...")
                            res = downloader_tab.download(url, str(target_dir.resolve()), f"img_{i+1}")
                            if res and res[0]:
                                downloaded_path = Path(res[1])
                                self._resize_image(downloaded_path)
                                if self._is_valid_image(downloaded_path):
                                    if desc: (target_dir / f"{downloaded_path.stem}.txt").write_text(desc, encoding='utf-8')
                                    local_paths[i] = downloaded_path
                                else:
                                    if downloaded_path.exists(): downloaded_path.unlink()

                    except Exception as e:
                        if self.debug:
                            print(f"      - Fallback {i+1} failed: {e}")
                
                # Close the fallback tab
                try:
                    downloader_tab.close()
                except:
                    pass

            except Exception as e:
                if self.debug:
                    print(f"    - Browser fallback error: {e}")
            
        return [p for p in local_paths if p is not None]

    def _download_single_requests(self, url: str, index: int, target_dir: Path, session, desc: str) -> Optional[Path]:
        """Layer 1: Download using requests with headers."""
        try:
            # Handle unicode escapes and unquote
            if r'\u' in url:
                url = url.encode().decode('unicode_escape')
            from urllib.parse import unquote, urlparse
            url = unquote(url)
            
            # SOTA: 使用目标域名的根路径作为 Referer 绕过热链保护
            parsed_url = urlparse(url)
            referer = f"{parsed_url.scheme}://{parsed_url.netloc}/"
            
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0'
            ]
            
            headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': referer,
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            time.sleep(random.uniform(0.1, 0.4))
            
            # SOTA: First attempt with full headers
            try:
                resp = session.get(url, headers=headers, timeout=25, verify=False, allow_redirects=True)
            except Exception as e:
                if self.debug: print(f"      [Layer 1] First attempt failed ({e}), trying Clean Header Fallback...")
                # Layer 1.1: Clean Header Fallback (strip Sec-Fetch and other complex tokens)
                clean_headers = {
                    'User-Agent': headers['User-Agent'],
                    'Accept': 'image/*',
                    'Referer': headers['Referer']
                }
                resp = session.get(url, headers=clean_headers, timeout=30, verify=False, allow_redirects=True)
            
            if resp.status_code == 200 and len(resp.content) > 2000:
                c_type = resp.headers.get('Content-Type', '').lower()
                ext = ".png" if 'png' in c_type else ".webp" if 'webp' in c_type else ".jpg"
                path = target_dir / f"img_{index+1}{ext}"
                path.write_bytes(resp.content)
                if desc:
                    (target_dir / f"img_{index+1}.txt").write_text(desc, encoding='utf-8')
                self._resize_image(path)
                
                # SOTA: Final integrity check
                if self._is_valid_image(path):
                    return path
                else:
                    if self.debug: 
                        print(f"      [Layer 1] Integrity check FAILED for {path.name}. Headers: {dict(resp.headers)}")
                    path.unlink(missing_ok=True)
                    return None
            elif self.debug:
                # SOTA Diagnostic: Capture the reason for failure
                print(f"      [Layer 1] FAILED: {resp.status_code} for {url[:60]}...")
                print(f"      [Layer 1] Response Headers: {json.dumps(dict(resp.headers), indent=2)}")
                if len(resp.content) <= 2000:
                    print(f"      [Layer 1] Warning: Payload too small ({len(resp.content)} bytes). Likely a block page.")
        except Exception as e:
            if self.debug:
                print(f"      [Layer 1] CRITICAL ERROR downloading {url[:60]}: {e}")
        return None

    def _resize_image(self, path: Path):
        """Resize image to 768px max side and convert to JPEG for Gemini Vision."""
        try:
            from PIL import Image
            with Image.open(path) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                if max(img.size) > 768:
                    img.thumbnail((768, 768), Image.Resampling.LANCZOS)
                    img.save(path, "JPEG", quality=80)
        except:
            pass

    def _is_valid_image(self, file_path: Path) -> bool:
        """Verify magic numbers and minimum file size."""
        if not file_path.exists():
            return False
        
        # SOTA: Minimum 2KB to filter out generic block pages or blank pixels
        if file_path.stat().st_size < 2048:
            return False
            
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
                # JPEG
                if header.startswith(b'\xff\xd8\xff'):
                    return True
                # PNG
                if header.startswith(b'\x89PNG\r\n\x1a\n'):
                    return True
                # WEBP
                if header.startswith(b'RIFF') and b'WEBP' in header:
                    return True
                # GIF
                if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
                    return True
        except:
            pass
            
        return False
