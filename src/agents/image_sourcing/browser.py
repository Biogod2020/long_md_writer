"""
BrowserManager: Encapsulates ChromiumPage lifecycle for reuse across search and download operations.
"""

import os
from DrissionPage import ChromiumOptions, ChromiumPage
from typing import Optional


class BrowserManager:
    """Manages a single ChromiumPage instance for reuse."""

    def __init__(self, headless: bool = True, debug: bool = False, block_resources: bool = False):
        self.headless = headless
        self.debug = debug
        self.block_resources = block_resources
        self._page: Optional[ChromiumPage] = None

    def _create_options(self) -> ChromiumOptions:
        """Create ChromiumOptions with standard settings."""
        co = ChromiumOptions()
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(chrome_path):
            co.set_browser_path(chrome_path)

        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--lang=en-US')
        co.set_pref('profile.default_content_setting_values.notifications', 2)
        co.auto_port()
        
        if self.block_resources:
            # Block images and other potentially heavy assets
            co.no_imgs() # DrissionPage helper to block images
            co.set_pref('profile.managed_default_content_settings.images', 2)
            co.set_argument('--blink-settings=imagesEnabled=false')
            # Note: We keep CSS enabled because some anti-bot challenges (Cloudflare) 
            # might require it for rendering the challenge box correctly.
        
        if self.headless:
            co.headless()
        
        return co

    @property
    def page(self) -> ChromiumPage:
        """Get or create the browser page instance."""
        if self._page is None:
            co = self._create_options()
            self._page = ChromiumPage(co)
            if self.debug:
                print("  [BrowserManager] Created new browser instance")
        return self._page

    def new_tab(self, url: Optional[str] = None):
        """Open a new tab in the browser."""
        if url:
            return self.page.new_tab(url)
        return self.page.new_tab()

    def quit(self):
        """Close the browser and release resources."""
        if self._page is not None:
            try:
                self._page.quit()
            except Exception:
                pass
            self._page = None
            if self.debug:
                print("  [BrowserManager] Browser closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        return False
