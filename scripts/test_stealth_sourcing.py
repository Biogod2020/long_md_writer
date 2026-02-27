from DrissionPage import ChromiumPage, ChromiumOptions
import time
import random
import os

def run_stealth_test():
    print("🚀 [STEALTH TEST] Testing Headless Google Sourcing...")
    
    co = ChromiumOptions()
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(chrome_path):
        co.set_browser_path(chrome_path)

    # 1. 基础反检测
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.headless(True) # 强制无头模式验证
    
    # 2. 指纹伪装
    # 使用最新的真实 Chrome UA
    real_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    co.set_user_agent(real_ua)
    
    # 3. 语言与窗口
    co.set_argument('--lang=en-US')
    co.set_argument('--window-size=1920,1080')
    
    # 指定一个隔离的测试 Profile 目录
    test_profile = os.path.abspath("./.gemini/stealth_test_profile")
    co.set_user_data_path(test_profile)
    co.auto_port()

    page = ChromiumPage(co)
    
    try:
        # 4. 模拟人类链路：首页 -> 搜索
        print("🌐 Step 1: Navigating to Google Home...")
        page.get("https://www.google.com")
        time.sleep(random.uniform(2, 4))
        
        # 检查是否已经撞墙
        if "sorry/index" in page.url:
            print("❌ FAILED: Blocked at homepage!")
            return False

        print("🔍 Step 2: Performing Search via UI interaction...")
        search_input = page.ele('name:q')
        if search_input:
            search_input.input("Einthoven triangle medical diagram")
            time.sleep(random.uniform(0.5, 1.5))
            search_input.run_js('this.form.submit()')
        else:
            # 兜底：直接跳转到图片搜索
            print("⚠️ Could not find search box, jumping to image search directly...")
            page.get("https://www.google.com/search?q=Einthoven+triangle+diagram&tbm=isch")

        time.sleep(random.uniform(3, 5))
        
        # 5. 结果验证
        print(f"📍 Current URL: {page.url[:80]}...")
        if "sorry/index" in page.url:
            print("❌ FAILED: Captcha detected after search!")
            return False
        
        # 尝试提取图片原始结果
        html = page.html
        if '["https://' in html:
            print("✅ SUCCESS! Found image JSON data in headless mode.")
            return True
        else:
            print("❓ WARNING: No image data found, but no Captcha either. Check page content.")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        page.quit()

if __name__ == "__main__":
    success = run_stealth_test()
    if success:
        print("\n🏆 Stealth strategy WORKS in Headless mode!")
    else:
        print("\n💀 Stealth strategy FAILED. Google is too smart.")
