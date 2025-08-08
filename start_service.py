#!/usr/bin/env python3
"""
Startup script for the Robust Web Scraping Service
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

def check_dependencies():
    """Check if all required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    try:
        import fastapi
        import playwright
        import tenacity
        import beautifulsoup4
        print("✅ All Python dependencies are installed")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False
    
    return True

def install_playwright_browsers():
    """Install Playwright browsers if not already installed"""
    print("🔧 Checking Playwright browsers...")
    
    try:
        # Check if playwright browsers are installed
        result = subprocess.run(
            ["playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True
        )
        
        if "chromium" not in result.stdout:
            print("📦 Installing Playwright browsers...")
            subprocess.run(["playwright", "install", "chromium"], check=True)
            subprocess.run(["playwright", "install-deps"], check=True)
            print("✅ Playwright browsers installed")
        else:
            print("✅ Playwright browsers already installed")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Playwright browsers: {e}")
        return False
    except FileNotFoundError:
        print("❌ Playwright not found. Please install it first:")
        print("   pip install playwright")
        print("   playwright install chromium")
        return False
    
    return True

def setup_environment():
    """Setup environment variables"""
    print("⚙️  Setting up environment...")
    
    # Set default port if not provided
    if not os.getenv("PORT"):
        os.environ["PORT"] = "8000"
    
    print(f"✅ Environment configured (PORT: {os.getenv('PORT')})")

def start_service():
    """Start the FastAPI service"""
    print("🚀 Starting Robust Web Scraping Service...")
    print("=" * 50)
    
    try:
        # Import and run the service
        from main import app
        import uvicorn
        
        port = int(os.getenv("PORT", 8000))
        
        print(f"🌐 Service will be available at: http://localhost:{port}")
        print("📚 API documentation: http://localhost:{port}/docs")
        print("🏥 Health check: http://localhost:{port}/health")
        print()
        print("Press Ctrl+C to stop the service")
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
    """Main startup function"""
    print("🚀 Robust Web Scraping Service - Startup")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Install Playwright browsers
    if not install_playwright_browsers():
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Start the service
    start_service()

if __name__ == "__main__":
    main()
