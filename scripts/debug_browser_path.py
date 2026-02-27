import os
import subprocess
from DrissionPage import ChromiumPage, ChromiumOptions

def find_chrome():
    print("🔎 Searching for Chrome/Chromium binaries...")
    paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/local/bin/google-chrome"
    ]
    
    found = []
    for p in paths:
        if os.path.exists(p):
            print(f"✅ Found: {p}")
            found.append(p)
        else:
            print(f"❌ Not found: {p}")
            
    # Try which command
    try:
        which_chrome = subprocess.check_output(['which', 'google-chrome'], stderr=subprocess.STDOUT).decode().strip()
        print(f"✅ Found via 'which': {which_chrome}")
        found.append(which_chrome)
    except:
        pass
        
    return found

def test_binary(path):
    print(f"\n--- Testing Binary: {path} ---")
    co = ChromiumOptions()
    co.set_browser_path(path)
    co.headless()
    try:
        page = ChromiumPage(co)
        print(f"✅ Successfully launched {path}")
        print(f"📍 Address: {page.address}")
        page.quit()
        return True
    except Exception as e:
        print(f"❌ Failed to launch {path}: {e}")
        return False

if __name__ == "__main__":
    binaries = find_chrome()
    if not binaries:
        print("🚨 CRITICAL: No browser binaries found on system.")
    else:
        for b in binaries:
            test_binary(b)
