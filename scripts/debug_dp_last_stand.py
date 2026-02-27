import os
import socket
import time
import subprocess
from DrissionPage import ChromiumPage, ChromiumOptions

def get_free_port():
    """Manually find a free port to avoid DP's auto_port bugs."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def last_chance_dp():
    print("🛡️ Attempting 'Last Stand' DrissionPage Fix...")
    
    # 1. Kill all potential interference
    os.environ['no_proxy'] = '*'
    os.environ['NO_PROXY'] = '*'
    
    try:
        if os.name != 'nt':
            subprocess.run(['pkill', '-9', 'Google Chrome'], capture_output=True)
    except: pass
    
    # 2. Pick a manual port
    port = get_free_port()
    print(f"📍 Manually selected port: {port}")
    
    # 3. Setup Options
    user_data = os.path.abspath("./.gemini/browser_profile_last_stand")
    os.makedirs(user_data, exist_ok=True)
    
    co = ChromiumOptions()
    co.set_local_port(port)
    co.set_user_data_path(user_data)
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    
    # Explicitly set the address string to bypass parsing bugs
    # address = f"127.0.0.1:{port}"
    
    try:
        print("🚀 Launching browser...")
        page = ChromiumPage(co)
        print(f"✅ ATTACHED! Address: {page.address}")
        
        print("🌐 Testing stealth navigation...")
        page.get("https://www.google.com", timeout=10)
        print(f"🎉 SUCCESS! Page title: {page.title}")
        
        page.quit()
        return True
    except Exception as e:
        print(f"❌ FAILED again: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    last_chance_dp()
