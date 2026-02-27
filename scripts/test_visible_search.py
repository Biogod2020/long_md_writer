from DrissionPage import ChromiumPage, ChromiumOptions
import time
import os

def test_visible_search():
    print("🚀 [DIAGNOSIS] Attempting to open a VISIBLE Google Search window...")
    
    co = ChromiumOptions()
    # 强制指定有头模式
    co.headless(False)
    
    # 显式指定 Chrome 路径
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        co.set_browser_path(chrome_path)
        print(f"📍 Using Chrome at: {chrome_path}")

    # 使用一个隔离的、全新的测试 Profile，防止锁冲突
    test_profile = os.path.abspath("./.gemini/diag_profile")
    if os.path.exists(test_profile):
        import shutil
        # 尝试清理旧的锁文件
        lock = os.path.join(test_profile, "SingletonLock")
        if os.path.exists(lock): os.unlink(lock)
        
    co.set_user_data_path(test_profile)
    # 不使用 auto_port，看看默认端口是否能行
    # co.auto_port() 

    try:
        print("⏳ Initializing Browser...")
        page = ChromiumPage(co)
        print("✅ Browser window should be open NOW!")
        
        url = "https://www.google.com/search?q=Einthoven+triangle+ECG&tbm=isch"
        print(f"🌐 Navigating to: {url}")
        page.get(url)
        
        print(f"📄 Page Title: {page.title}")
        print("\n👉 DO YOU SEE THE BROWSER WINDOW?")
        print("👉 If you see a CAPTCHA, please solve it manually now.")
        
        # 保持窗口打开 30 秒供操作
        for i in range(30):
            print(f"Time remaining: {30-i}s", end="\r")
            time.sleep(1)
            
        print("\n🏁 Diagnosis script complete.")
        page.quit()

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_visible_search()
