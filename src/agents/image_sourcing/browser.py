"""
BrowserManager: Encapsulates ChromiumPage lifecycle for reuse across search and download operations.
Hardened for SOTA 2.1 with Proxy Armor and Manual Port cycling.
"""

import os
import socket
import subprocess
from DrissionPage import ChromiumOptions, ChromiumPage
from typing import Optional


class BrowserManager:
    """Manages a stable ChromiumPage instance with Manual Port cycling and Proxy Armor."""

    def __init__(self, headless: bool = True, debug: bool = False, block_resources: bool = False):
        self.headless = headless
        self.debug = debug
        self.block_resources = block_resources
        self._page: Optional[ChromiumPage] = None
        
        # SOTA: Proxy Armor - Force local traffic to bypass VPN/Proxy to avoid WebSocket deadlocks
        os.environ['no_proxy'] = '*'
        os.environ['NO_PROXY'] = '*'
        
        # SOTA: Return to a single, stable profile to maintain long-term session/cookies
        self.user_data_dir = os.path.abspath("./.gemini/browser_profile_stable")
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        # SOTA: Self-healing for Chrome singleton lock
        self._clear_singleton_lock()

    def _get_free_port(self) -> int:
        """Manually find an available port to avoid DrissionPage's internal auto_port bugs."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def _clear_singleton_lock(self):
        """Removes Chrome lock files and cleans up zombie processes for the profile."""
        lock_file = os.path.join(self.user_data_dir, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.unlink(lock_file)
                if self.debug: print(f"  [BrowserManager] Physical lock cleared: {lock_file}")
            except: pass
        
        try:
            if os.name != 'nt': # Unix/Mac
                subprocess.run(['pkill', '-9', '-f', self.user_data_dir], capture_output=True)
        except: pass

    def _create_options(self, force_headless: Optional[bool] = None) -> ChromiumOptions:
        """Create ChromiumOptions with stability and stealth settings."""
        co = ChromiumOptions()
        
        # Stability arguments
        co.set_argument('--no-first-run')
        co.set_argument('--no-default-browser-check')
        co.set_argument('--disable-background-networking')
        co.set_argument('--disable-sync')
        co.set_argument('--disable-translate')
        co.set_argument('--hide-scrollbars')
        co.set_argument('--mute-audio')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(chrome_path):
            co.set_browser_path(chrome_path)

        # Basic anti-bot bypass
        co.set_argument('--lang=en-US')
        co.set_argument('--disable-blink-features=AutomationControlled') 
        
        # SOTA: Use fixed user data dir to keep Google's NID cookies
        co.set_user_data_path(self.user_data_dir)
        
        # Determine headless mode
        h_mode = force_headless if force_headless is not None else self.headless
        if h_mode:
            co.headless()
        
        if self.block_resources and force_headless is not False:
            co.no_imgs()
            co.set_pref('profile.default_content_setting_values.notifications', 2)
            co.set_argument('--blink-settings=imagesEnabled=false')
        
        return co

    @property
    def page(self) -> ChromiumPage:
        """Get or create the browser page instance with hardened initialization."""
        try:
            if self._page is not None:
                # Trigger a simple property check to verify connection
                _ = self._page.address
        except Exception:
            if self.debug: print("  [BrowserManager] ⚠️ Connection lost. Resetting browser...")
            self.quit()

        if self._page is None:
            self._clear_singleton_lock()
            
            # SOTA 2.1: Manual Port Assignment logic to bypass internal DP bugs
            port = self._get_free_port()
            if self.debug: print(f"  [BrowserManager] Launching Chrome on Manual Port: {port}")
            
            co = self._create_options()
            co.set_local_port(port)
            
            try:
                self._page = ChromiumPage(co)
                if self.debug: print(f"  [BrowserManager] Browser successfully attached to port {port}")
            except Exception as e:
                if self.debug: print(f"  [BrowserManager] ❌ Physical attachment failed: {e}. Retrying once...")
                self._clear_singleton_lock()
                co.set_local_port(self._get_free_port())
                self._page = ChromiumPage(co)
                
        return self._page

    def check_and_rescue(self, tab, target_url: str) -> bool:
        """
        SOTA: Detects CAPTCHA and triggers interactive rescue UI.
        Returns True if a rescue was performed.
        """
        if "sorry/index" not in tab.url:
            return False

        import time
        print("\n" + "!"*60)
        print("⚠️  [BROWSER RESCUE] GOOGLE CAPTCHA DETECTED!")
        print(f"📍 Target: {target_url[:60]}...")
        print("🚀 Escalating to VISIBLE mode for manual rescue...")
        print("!"*60 + "\n")

        # 1. Shutdown the invisible one
        self.quit()
        time.sleep(1)

        # 2. Relaunch in Headful mode
        co = self._create_options(force_headless=False)
        # SOTA: Still use manual port for rescue
        port = self._get_free_port()
        co.set_local_port(port)
        self._page = ChromiumPage(co)
        
        # 3. Navigate back to target
        rescue_tab = self._page.new_tab(target_url)
        
        print("👉 ACTION REQUIRED: Please solve the CAPTCHA in the browser window.")
        print("👉 I am monitoring... once solved, I will automatically resume.")

        # 4. Monitor solve
        start_time = time.time()
        solved = False
        while time.time() - start_time < 300: # 5 min limit
            if "sorry/index" not in rescue_tab.url and '["https://' in rescue_tab.html:
                print("\n✅ [RESCUE] Success! Session cleaned. Resuming...")
                solved = True
                break
            time.sleep(1)
        
        if not solved:
            print("\n❌ [RESCUE] Failed or timed out.")
            return False

        # 5. SOTA: Return to Headless mode while keeping the solved session
        print("✅ [RESCUE] Reverting to Headless mode for background processing...")
        self.quit()
        time.sleep(1)
        
        # This will trigger a fresh, headless relaunch on next .page access
        return True

    def new_tab(self, url: Optional[str] = None):
        """Open a new tab in the browser."""
        if url:
            return self.page.new_tab(url)
        return self.page.new_tab()

    def quit(self):
        """Close the browser and release resources with Hard Kill safety."""
        if self._page is not None:
            try:
                self._page.quit()
            except Exception:
                pass
            self._page = None
        
        # SOTA: Hard physical cleanup to prevent zombie processes from holding the profile lock
        self._clear_singleton_lock()
        
        if self.debug: print("  [BrowserManager] Browser resources released and locks cleared.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        return False
