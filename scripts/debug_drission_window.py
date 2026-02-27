from DrissionPage import ChromiumPage, ChromiumOptions
import time
import os

print("🚀 [DEBUG] Attempting to open a VISIBLE browser window...")

co = ChromiumOptions()
# 显式指定 Chrome 路径（macOS 标准路径）
chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if os.path.exists(chrome_path):
    co.set_browser_path(chrome_path)
    print(f"📍 Using Chrome at: {chrome_path}")

# 强制有头模式
co.headless(False)
# 禁用沙盒和一些干扰项
co.set_argument('--no-sandbox')
co.set_argument('--disable-gpu')

try:
    print("⏳ Initializing ChromiumPage...")
    page = ChromiumPage(co)
    print("✅ Browser instance created!")
    
    url = "https://www.google.com"
    print(f"🌐 Navigating to {url}...")
    page.get(url)
    
    print(f"📄 Current Title: {page.title}")
    print("\n👉 DO YOU SEE A WINDOW? (Waiting 15 seconds before closing...)")
    
    # 保持窗口打开供观察
    for i in range(15):
        print(f"Time remaining: {15-i}s", end="\r")
        time.sleep(1)
        
    page.quit()
    print("\n🏁 Debug script finished.")

except Exception as e:
    print(f"\n❌ FAILED to open window: {e}")
    import traceback
    traceback.print_exc()
