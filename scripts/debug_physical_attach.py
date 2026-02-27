import os
import subprocess
import time
from DrissionPage import ChromiumPage, ChromiumOptions

def force_kill_chrome():
    print("🧹 Killing all existing Chrome processes...")
    if os.name != 'nt':
        subprocess.run(['pkill', '-9', 'Google Chrome'], capture_output=True)
        subprocess.run(['pkill', '-9', 'Chromium'], capture_output=True)
    time.sleep(1)

def physical_launch():
    force_kill_chrome()
    
    # 1. Prepare Profile
    user_data = os.path.abspath("./.gemini/browser_profile_debug")
    os.makedirs(user_data, exist_ok=True)
    lock_file = os.path.join(user_data, "SingletonLock")
    if os.path.exists(lock_file): os.unlink(lock_file)
    
    # 2. Launch Command
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_path,
        f"--remote-debugging-port=9222",
        f"--user-data-dir={user_data}",
        "--no-first-run",
        "--no-default-browser-check",
        "--headless=new" # Let's try new headless first
    ]
    
    print(f"🚀 Manually launching: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3) # Wait for startup
    
    # 3. Try to attach
    print("🔗 Attempting to attach DrissionPage to port 9222...")
    try:
        co = ChromiumOptions()
        co.set_local_port(9222)
        # SOTA: Do NOT set browser path here, we want to attach to the existing one
        page = ChromiumPage(co)
        print(f"✅ Successfully attached! Address: {page.address}")
        print("🌐 Navigating to Google...")
        page.get("https://www.google.com", timeout=10)
        print(f"🎉 SUCCESS! Page title: {page.title}")
        page.quit()
        return True
    except Exception as e:
        print(f"❌ Attachment failed: {e}")
        return False
    finally:
        proc.kill()

if __name__ == "__main__":
    physical_launch()
