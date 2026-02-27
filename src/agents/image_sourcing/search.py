"""
GoogleImageSearcher: Logic for searching Google Images and extracting candidate URLs.
"""

import re
import requests
import time
from typing import List, Dict
from .browser import BrowserManager


class GoogleImageSearcher:
    """Searches Google Images using a DrissionPage browser instance."""

    def __init__(self, browser_manager: BrowserManager, debug: bool = False):
        self.browser_manager = browser_manager
        self.debug = debug

    def search(self, queries: List[str]) -> List[Dict[str, str]]:
        """
        Search Google Images using parallel tab loading.
        
        Opens all tabs simultaneously, then waits and processes them.
        """
        if self.debug:
            print(f"    - Search Queries: {queries}")
            
        all_candidates = []
        page = self.browser_manager.page
        tabs = []
        
        try:
            # 1. Open all tabs simultaneously
            for q_idx, query in enumerate(queries[:2]):
                encoded_query = requests.utils.quote(query)
                url = f'https://www.google.com/search?q={encoded_query}&tbm=isch&tbs=isz:m&hl=en&gl=us'
                
                if q_idx == 0:
                    page.get(url)
                    tabs.append(page)
                else:
                    tabs.append(page.new_tab(url))
                
                if self.debug:
                    print(f"      - Tab {q_idx+1}: Opened {url[:60]}...")
            
            # 2. Wait for all tabs to load (smart waiting with 8s timeout)
            for q_idx, tab in enumerate(tabs):
                try:
                    tab.wait.doc_loaded(timeout=8)
                except:
                    time.sleep(2)  # Brief fallback if wait fails
                
                if self.debug:
                    print(f"      - Tab {q_idx+1}: Loaded {tab.url[:60]}...")
            
            # 3. Process each tab
            for q_idx, tab in enumerate(tabs):
                # SOTA: Check for CAPTCHA and trigger Manual Rescue UI if needed
                if "sorry/index" in tab.url:
                    print(f"      - [!] Google Captcha detected on Tab {q_idx+1}")
                    target_url = tab.url
                    # Trigger physical rescue
                    if self.browser_manager.check_and_rescue(tab, target_url):
                        print(f"      - [RESCUE] Session recovered. Re-extracting for Tab {q_idx+1}...")
                        # RE-ACQUIRE: Rescue logic relaunches the browser. We MUST refresh our references.
                        page = self.browser_manager.page
                        # SOTA: Use get_tab() to acquire the newly opened tab in the headful instance
                        tab = page.get_tab()
                        if "google.com/search" not in tab.url:
                            tab.get(target_url)
                        
                        # Give it time to render the results
                        tab.wait.doc_loaded(timeout=5)
                    else:
                        continue

                page_html = tab.html
                tab_candidates = self._extract_candidates(page_html)
                
                if tab_candidates:
                    if self.debug:
                        print(f"      - Found {len(tab_candidates)} raw candidates.")
                    for c in tab_candidates:
                        if c['url'] not in [x['url'] for x in all_candidates]:
                            all_candidates.append(c)
                else:
                    if self.debug:
                        print(f"      - Tab {q_idx+1}: No candidates found in HTML.")

            # 4. Close extra tabs
            for i in range(1, len(tabs)):
                try:
                    tabs[i].close()
                except:
                    pass
                    
        except Exception as e:
            if self.debug:
                print(f"    - Search error: {e}")
        
        # Deduplicate
        seen = set()
        unique = []
        for c in all_candidates:
            if c['url'] not in seen:
                seen.add(c['url'])
                unique.append(c)
        return unique

    def _extract_candidates(self, page_html: str) -> List[Dict[str, str]]:
        """Extract image URLs and titles from page HTML."""
        candidates = []
        
        # Pattern for Google image source arrays
        regex = r'\["(https?://[^"]+?\.(?:jpg|png|jpeg|webp|gif)[^"]*?)",(\d+),(\d+)\]'
        
        for match in re.finditer(regex, page_html):
            m_url = match.group(1)
            clean_url = m_url.replace('\\u003d', '=').replace('\\u0026', '&')
            if 'gstatic.com' not in clean_url and 'encrypted-tbn' not in clean_url:
                # Extract title nearby
                search_area = page_html[match.end():match.end()+1000]
                title_match = re.search(r'"2003":\[null,"[^"]*","[^"]*","([^"]+)"', search_area)
                title = title_match.group(1) if title_match else "Search result"
                
                candidates.append({
                    'url': clean_url,
                    'desc': title
                })

        # Fallback: simple harvesting
        if len(candidates) < 5:
            simple_regex = r'"(https?://[^"]+?\.(?:jpg|png|jpeg|webp|gif)[^"]*?)"'
            simple_matches = re.findall(simple_regex, page_html)
            for s_url in simple_matches:
                clean_url = s_url.replace('\\u003d', '=').replace('\\u0026', '&')
                if 'gstatic.com' not in clean_url and 'encrypted-tbn' not in clean_url:
                    if not any(c['url'] == clean_url for c in candidates):
                        candidates.append({
                            'url': clean_url,
                            'desc': "Simple harvest"
                        })
        
        return candidates
