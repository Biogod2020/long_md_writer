from DrissionPage import ChromiumPage, ChromiumOptions
import time
import os

def test_headless_after_manual():
    print("🚀 [VERIFICATION] Testing HEADLESS search using the cleaned profile...")
    
    co = ChromiumOptions()
    # 强制无头模式
    co.headless(True)
    
    # 指向刚才人工操作过的 Profile
    test_profile = os.path.abspath("./.gemini/diag_profile")
    co.set_user_data_path(test_profile)
    
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        co.set_browser_path(chrome_path)

    # 基础反检测
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')

    try:
        page = ChromiumPage(co)
        
        # 使用一个新的查询，确保不是缓存
        query = "Augustus Waller capillary electrometer"
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"
        
        print(f"🌐 Navigating Headless to: {url}")
        page.get(url)
        
        print(f"📍 Current URL: {page.url}")
        print(f"📄 Page Title: {page.title}")
        
        if "sorry/index" in page.url:
            print("❌ FAILED: Captcha detected even after manual cleaning!")
        else:
            # 检查是否有图片特征数据
            html = page.html
            if '["https://' in html:
                print("✅ SUCCESS! Headless mode is now working with the existing Session.")
            else:
                print("❓ WARNING: No Captcha, but no image data found either. Check page source.")
        
        page.quit()

    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_headless_after_manual()
