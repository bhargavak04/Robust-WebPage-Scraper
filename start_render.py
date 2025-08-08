#!/usr/bin/env python3
"""
Startup script for Render deployment with Playwright browser installation
"""

import os
import sys
import subprocess
import logging

def install_playwright_browsers():
    """Install Playwright browsers directly"""
    print("🔧 Installing Playwright browsers...")
    
    # Check if browser already exists
    browser_path = "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome"
    if os.path.exists(browser_path):
        print("✅ Browser already exists")
        return True
    
    # Method 1: Direct playwright install
    try:
        print("📦 Method 1: Direct playwright install")
        result = subprocess.run(
            ["playwright", "install", "chromium", "--with-deps"],
            capture_output=True,
            text=True,
            timeout=300
        )
        print(f"Installation output: {result.stdout}")
        if result.stderr:
            print(f"Installation stderr: {result.stderr}")
        
        if result.returncode == 0 and os.path.exists(browser_path):
            print("✅ Direct installation successful")
            return True
        else:
            print(f"❌ Direct installation failed with code {result.returncode}")
    except Exception as e:
        print(f"❌ Direct installation error: {e}")
    
    # Method 2: Force reinstall
    try:
        print("📦 Method 2: Force reinstall")
        result = subprocess.run(
            ["playwright", "install", "chromium", "--force", "--with-deps"],
            capture_output=True,
            text=True,
            timeout=300
        )
        print(f"Force install output: {result.stdout}")
        if result.stderr:
            print(f"Force install stderr: {result.stderr}")
        
        if result.returncode == 0 and os.path.exists(browser_path):
            print("✅ Force installation successful")
            return True
        else:
            print(f"❌ Force installation failed with code {result.returncode}")
    except Exception as e:
        print(f"❌ Force installation error: {e}")
    
    # Method 3: Manual browser setup
    try:
        print("📦 Method 3: Manual browser setup")
        # Create cache directory
        cache_dir = "/home/scraper/.cache/ms-playwright"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Try to find existing browser in other locations
        possible_paths = [
            "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
            "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/chrome"
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                print(f"✅ Found existing browser at: {path}")
                # Copy to expected location
                target_dir = "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux"
                os.makedirs(target_dir, exist_ok=True)
                import shutil
                shutil.copy2(path, f"{target_dir}/chrome")
                os.chmod(f"{target_dir}/chrome", 0o755)
                print("✅ Browser copied to expected location")
                return True
    except Exception as e:
        print(f"❌ Manual setup error: {e}")
    
    print("❌ All installation methods failed")
    return False

def start_service():
    """Start the FastAPI service"""
    print("🚀 Starting Robust Web Scraping Service on Render...")
    print("=" * 50)
    
    try:
        # Import and run the service
        from main import app
        import uvicorn
        
        port = int(os.getenv("PORT", 8000))
        
        print(f"🌐 Service will be available on port: {port}")
        print("📚 API documentation: /docs")
        print("🏥 Health check: /health")
        print("=" * 50)
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n⚠️  Service stopped by user")
    except Exception as e:
        print(f"❌ Error starting service: {e}")
        sys.exit(1)

def main():
    """Main startup function for Render"""
    print("🚀 Robust Web Scraping Service - Render Startup")
    print("=" * 50)
    
    # Install Playwright browsers
    if not install_playwright_browsers():
        print("❌ Failed to install Playwright browsers")
        sys.exit(1)
    
    # Test browser installation
    try:
        print("🧪 Testing browser installation...")
        result = subprocess.run(
            ["python", "test_browser.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(f"Browser test output: {result.stdout}")
        if result.stderr:
            print(f"Browser test errors: {result.stderr}")
        
        if result.returncode != 0:
            print("❌ Browser test failed, but continuing...")
        else:
            print("✅ Browser test passed!")
    except Exception as e:
        print(f"❌ Browser test error: {e}")
    
    # Start the service
    start_service()

if __name__ == "__main__":
    main()
