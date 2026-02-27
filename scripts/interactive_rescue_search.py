from DrissionPage import ChromiumPage, ChromiumOptions
import time
import os
import sys

def run_interactive_rescue():
    profile_path = os.path.abspath("./.gemini/browser_profile_stable")
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    def get_co(headless=True):
        co = ChromiumOptions()
        if os.path.exists(chrome_path): co.set_browser_path(chrome_path)
        co.set_user_data_path(profile_path)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.set_argument('--no-sandbox')
        if headless: co.headless(True)
        else: co.headless(False)
        return co

    print(f"🚀 [RESCUE] Starting search session with profile: {profile_path}")
    
    # --- STEP 1: INITIAL CHECK ---
    page = ChromiumPage(get_co(headless=True))
    query = "Einthoven triangle historical diagram"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"
    
    print(f"🌐 Checking status for: {query}...")
    page.get(url)
    
    if "sorry/index" not in page.url:
        print("✅ No Captcha detected! Headless mode is working.")
        page.quit()
        return True

    # --- STEP 2: MANUAL RESCUE ---
    print("\n⚠️ [!] GOOGLE CAPTCHA DETECTED!")
    print("📢 Switching to VISIBLE mode for manual rescue...")
    page.quit() # Close headless
    
    # Launch headful
    page = ChromiumPage(get_co(headless=False))
    page.get(url)
    
    print("\n👉 ACTION REQUIRED: Please solve the CAPTCHA in the browser window.")
    print("👉 I am monitoring the window... once you solve it, I will continue.")
    
    # Monitor loop
    start_time = time.time()
    solved = False
    while time.time() - start_time < 300: # 5 minute timeout
        if "sorry/index" not in page.url and '["https://' in page.html:
            print("\n🎉 SIGNAL RECEIVED: Captcha solved and results detected!")
            solved = True
            break
        print("⏳ Waiting for you to solve the Captcha... (URL: sorry/index)", end="\r")
        time.sleep(1)
    
    if not solved:
        print("\n❌ Timeout or failed to solve.")
        page.quit()
        return False

    print("💾 Session solidified. Closing visible window and verifying headless...")
    page.quit()
    
    # --- STEP 3: FINAL VERIFICATION ---
    time.sleep(2)
    page = ChromiumPage(get_co(headless=True))
    verify_query = "Willem Einthoven 1924 Nobel Prize"
    v_url = f"https://www.google.com/search?q={verify_query.replace(' ', '+')}&tbm=isch"
    
    print(f"🌐 Final Verification (Headless): {verify_query}...")
    page.get(v_url)
    
    if "sorry/index" in page.url:
        print("💀 FAILED: Google still detects automation even after manual cleaning.")
        page.quit()
        return False
    else:
        print("🏆 SUCCESS! Headless mode is now fully operational with the cleaned session.")
        page.quit()
        return True

if __name__ == "__main__":
    run_interactive_rescue()
