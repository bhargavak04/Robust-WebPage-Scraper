#!/usr/bin/env python3
"""
Simple browser installation script
"""

import subprocess
import os
import sys

def install_browser():
    """Install Playwright browser"""
    print("🔧 Installing Playwright browser...")
    
    try:
        # Install browser
        result = subprocess.run(
            ["playwright", "install", "chromium", "--with-deps"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        print(f"Installation output: {result.stdout}")
        if result.stderr:
            print(f"Installation errors: {result.stderr}")
        
        if result.returncode == 0:
            print("✅ Browser installation successful")
            
            # Check if browser exists
            browser_path = "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome"
            if os.path.exists(browser_path):
                print(f"✅ Browser found at: {browser_path}")
                return True
            else:
                print(f"❌ Browser not found at expected path: {browser_path}")
                return False
        else:
            print(f"❌ Browser installation failed with code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Browser installation error: {e}")
        return False

if __name__ == "__main__":
    success = install_browser()
    sys.exit(0 if success else 1)
