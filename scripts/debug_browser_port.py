from DrissionPage import ChromiumPage, ChromiumOptions
import time
import os

def test_init_strategy(name, options):
    print(f"\n--- Testing Strategy: {name} ---")
    start_time = time.time()
    try:
        # We will try to open a simple page
        page = ChromiumPage(options)
        print(f"✅ Browser process started (Port: {page.address})")
        
        print("🌐 Attempting to load about:blank...")
        page.get("about:blank", timeout=10)
        print(f"📄 Page Title: '{page.title}'")
        
        print("🌐 Attempting to load https://www.google.com ...")
        page.get("https://www.google.com", timeout=15)
        print(f"✅ Navigation successful! Title: {page.title}")
        
        time.sleep(2) # Keep it open for a moment
        page.quit()
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 DIAGNOSTIC: DrissionPage Page Responsiveness")
    
    # Strategy 1: Visible (Headful) - This lets you see if it's stuck on a cert or loading
    co1 = ChromiumOptions()
    # Explicitly set headful
    # co1.headless(False) # Default is False, but let's be explicit
    co1.set_argument('--no-sandbox')
    co1.set_argument('--disable-gpu')
    test_init_strategy("Visible Mode + No-GPU", co1)
    
    # Strategy 2: New Headless mode (sometimes more stable on Mac)
    co2 = ChromiumOptions()
    co2.headless(True)
    co2.set_argument('--headless=new') 
    co2.set_argument('--disable-gpu')
    test_init_strategy("Headless New + No-GPU", co2)
    
    # Strategy 3: Extreme minimal (Disable everything)
    co3 = ChromiumOptions()
    co3.headless(True)
    co3.set_argument('--disable-extensions')
    co3.set_argument('--disable-background-networking')
    co3.set_argument('--disable-sync')
    co3.set_argument('--disable-default-apps')
    co3.set_argument('--mute-audio')
    co3.set_argument('--no-first-run')
    test_init_strategy("Extreme Minimal Headless", co3)
