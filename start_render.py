#!/usr/bin/env python3
"""
Startup script for Render deployment with Playwright browser installation
"""

import os
import sys
import subprocess
import logging

def install_playwright_browsers():
    """Install Playwright browsers if not already installed"""
    print("🔧 Installing Playwright browsers...")
    
    try:
        # Install chromium browser
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("✅ Chromium browser installed")
        
        # Install system dependencies
        subprocess.run(["playwright", "install-deps", "chromium"], check=True)
        print("✅ System dependencies installed")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Playwright browsers: {e}")
        return False
    except FileNotFoundError:
        print("❌ Playwright not found")
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
    
    # Start the service
    start_service()

if __name__ == "__main__":
    main()
