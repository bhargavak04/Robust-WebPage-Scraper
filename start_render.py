#!/usr/bin/env python3
"""
Startup script for Render deployment with Playwright browser installation
"""

import os
import sys
import subprocess
import logging

def install_playwright_browsers():
    """Install Playwright browsers using comprehensive installation script"""
    print("🔧 Installing Playwright browsers...")
    
    try:
        # Run the comprehensive installation script
        result = subprocess.run(
            ["python", "install_browsers.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )
        
        print(f"Installation output: {result.stdout}")
        if result.stderr:
            print(f"Installation errors: {result.stderr}")
        
        if result.returncode == 0:
            print("✅ Browser installation successful")
            return True
        else:
            print(f"❌ Browser installation failed with code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Browser installation timed out")
        return False
    except Exception as e:
        print(f"❌ Error running browser installation: {e}")
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
