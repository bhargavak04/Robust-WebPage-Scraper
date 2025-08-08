#!/usr/bin/env python3
"""
Comprehensive browser installation script for Render deployment
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_browser_exists():
    """Check if browser exists in common locations"""
    possible_paths = [
        "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        os.path.expanduser("~/.cache/ms-playwright/chromium-1091/chrome-linux/chrome")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Browser found at: {path}")
            return path
    return None

def install_browsers():
    """Install Playwright browsers with multiple fallback methods"""
    print("🔧 Installing Playwright browsers...")
    
    # Method 1: Standard installation
    try:
        print("📦 Method 1: Standard playwright install")
        result = subprocess.run(
            ["playwright", "install", "chromium", "--with-deps"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            print("✅ Standard installation successful")
            if check_browser_exists():
                return True
        else:
            print(f"❌ Standard installation failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Standard installation error: {e}")
    
    # Method 2: Force reinstall
    try:
        print("📦 Method 2: Force reinstall")
        result = subprocess.run(
            ["playwright", "install", "chromium", "--force", "--with-deps"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            print("✅ Force reinstall successful")
            if check_browser_exists():
                return True
        else:
            print(f"❌ Force reinstall failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Force reinstall error: {e}")
    
    # Method 3: Manual download
    try:
        print("📦 Method 3: Manual browser setup")
        # Create cache directory
        cache_dir = Path("/home/scraper/.cache/ms-playwright")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to find existing browser in other locations
        for root, dirs, files in os.walk("/"):
            if "chrome-linux" in dirs and "chrome" in files:
                chrome_path = os.path.join(root, "chrome")
                if os.path.isfile(chrome_path) and os.access(chrome_path, os.X_OK):
                    print(f"✅ Found existing browser at: {chrome_path}")
                    # Copy to expected location
                    target_dir = cache_dir / "chromium-1091" / "chrome-linux"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(chrome_path, target_dir / "chrome")
                    return True
    except Exception as e:
        print(f"❌ Manual setup error: {e}")
    
    return False

def verify_installation():
    """Verify browser installation"""
    print("🔍 Verifying browser installation...")
    
    browser_path = check_browser_exists()
    if browser_path:
        # Test if executable
        if os.access(browser_path, os.X_OK):
            print("✅ Browser is executable")
            return True
        else:
            print("❌ Browser is not executable")
            # Make executable
            try:
                os.chmod(browser_path, 0o755)
                print("✅ Made browser executable")
                return True
            except Exception as e:
                print(f"❌ Failed to make executable: {e}")
                return False
    else:
        print("❌ Browser not found")
        return False

def main():
    """Main installation function"""
    print("🚀 Playwright Browser Installation for Render")
    print("=" * 50)
    
    # Check if already installed
    if check_browser_exists():
        print("✅ Browser already installed")
        if verify_installation():
            print("🎉 Browser installation verified!")
            return True
    
    # Install browsers
    if install_browsers():
        if verify_installation():
            print("🎉 Browser installation successful!")
            return True
    
    print("❌ Browser installation failed")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
