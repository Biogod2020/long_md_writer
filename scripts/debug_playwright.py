import asyncio
import os
from playwright.async_api import async_playwright

async def test_playwright():
    print("🎭 Testing Playwright Connectivity...")
    try:
        async with async_playwright() as p:
            print("🚀 Launching Chromium...")
            # Use a fresh, unique user data dir
            user_data = os.path.abspath("./.gemini/playwright_test")
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data,
                headless=True,
                args=['--no-sandbox', '--disable-gpu']
            )
            print("✅ Browser launched.")
            
            page = await browser.new_page()
            print("🌐 Navigating to Google...")
            await page.goto("https://www.google.com", timeout=15000)
            title = await page.title()
            print(f"🎉 SUCCESS! Title: {title}")
            
            await browser.close()
            return True
    except Exception as e:
        print(f"❌ Playwright failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_playwright())
