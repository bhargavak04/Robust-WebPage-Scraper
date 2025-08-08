#!/usr/bin/env python3
"""
Test script to verify browser installation and functionality
"""

import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

async def test_browser_installation():
    """Test if browser is properly installed"""
    print("🔍 Testing browser installation...")
    
    # Check if browser exists
    browser_paths = [
        "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome"
    ]
    
    found_browser = None
    for path in browser_paths:
        if os.path.exists(path):
            print(f"✅ Browser found at: {path}")
            if os.access(path, os.X_OK):
                print(f"✅ Browser is executable: {path}")
                found_browser = path
                break
            else:
                print(f"❌ Browser not executable: {path}")
        else:
            print(f"❌ Browser not found: {path}")
    
    if not found_browser:
        print("❌ No executable browser found")
        return False
    
    # Test browser launch
    try:
        print("🚀 Testing browser launch...")
        playwright = await async_playwright().start()
        
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=found_browser,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        page = await browser.new_page()
        await page.goto('https://example.com')
        title = await page.title()
        print(f"✅ Browser test successful! Page title: {title}")
        
        await browser.close()
        await playwright.stop()
        return True
        
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        return False

def test_playwright_install():
    """Test playwright installation"""
    print("🔍 Testing playwright installation...")
    
    try:
        result = subprocess.run(
            ["playwright", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Playwright installed: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Playwright not working: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Playwright test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Browser Installation Test")
    print("=" * 40)
    
    # Test playwright installation
    if not test_playwright_install():
        print("❌ Playwright installation test failed")
        return False
    
    # Test browser installation
    if not await test_browser_installation():
        print("❌ Browser installation test failed")
        return False
    
    print("🎉 All tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
