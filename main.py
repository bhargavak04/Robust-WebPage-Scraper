import os
import json
import logging
import random
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import uvicorn

from scraper import WebScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global scraper instance for reuse
global_scraper = None
scraper_lock = asyncio.Lock()

# In-memory job storage (use Redis in production)
active_jobs = {}

# Configuration for Render.com free tier
RENDER_CONFIG = {
    'MAX_ARTICLES_PER_BATCH': 15,  # Reduced for free tier
    'MAX_CONCURRENT_ARTICLES': 3,  # Limit parallelism
    'REQUEST_TIMEOUT': 4 * 60,     # 4 minutes max
    'BATCH_SIZE': 5,               # Process in smaller batches
    'MAX_TOTAL_ARTICLES': 25,      # Hard limit to prevent timeouts
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global global_scraper
    
    # Startup
    logger.info("🚀 Starting up scraper service...")
    ensure_browser_installed()
    
    # Pre-initialize scraper for faster requests
    try:
        global_scraper = WebScraper()
        await global_scraper.__aenter__()
        logger.info("✅ Global scraper initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize global scraper: {e}")
        global_scraper = None
    
    yield
    
    # Shutdown
    if global_scraper:
        try:
            await global_scraper.__aexit__(None, None, None)
            logger.info("✅ Global scraper cleaned up")
        except Exception as e:
            logger.error(f"❌ Error cleaning up scraper: {e}")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Optimized Web Scraping Service",
    description="A production-grade web scraping service optimized for Render.com",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enhanced Pydantic models
class ScrapeRequest(BaseModel):
    base_urls: List[HttpUrl]
    max_articles_per_url: Optional[int] = RENDER_CONFIG['MAX_ARTICLES_PER_BATCH']
    delay_range: Optional[tuple] = (1, 2)  # Reduced delay for faster processing
    enable_streaming: Optional[bool] = True  # New: Enable streaming responses
    timeout_minutes: Optional[int] = 4       # New: Configurable timeout

class BatchScrapeRequest(BaseModel):
    base_urls: List[HttpUrl]
    batch_size: Optional[int] = RENDER_CONFIG['BATCH_SIZE']
    max_articles_per_url: Optional[int] = RENDER_CONFIG['MAX_ARTICLES_PER_BATCH']

class JobStatus(BaseModel):
    job_id: str
    status: str  # 'running', 'completed', 'failed', 'timeout'
    progress: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ScrapeResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]
    timestamp: str
    total_urls_processed: int
    total_articles_found: int
    processing_time_seconds: float
    job_id: Optional[str] = None

# Browser installation (optimized)
def ensure_browser_installed():
    """Optimized browser installation check"""
    import subprocess
    import os
    
    # Check multiple possible browser locations
    browser_paths = [
        "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome"
    ]
    
    for browser_path in browser_paths:
        if os.path.exists(browser_path):
            logger.info(f"✅ Browser found at {browser_path}")
            return True
    
    logger.info("🔧 Installing Playwright browser (optimized)...")
    
    try:
        # Single, most reliable installation method
        result = subprocess.run(
            ["playwright", "install", "chromium", "--with-deps"],
            capture_output=True,
            text=True,
            timeout=180,  # Reduced timeout
            env={**os.environ, "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "0"}
        )
        
        if result.returncode == 0:
            logger.info("✅ Browser installation successful")
            return True
        else:
            logger.error(f"❌ Browser installation failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Browser installation error: {e}")
        return False

# Helper function to get or create scraper
async def get_scraper():
    """Get global scraper or create new one if needed"""
    global global_scraper
    
    async with scraper_lock:
        if global_scraper is None:
            try:
                global_scraper = WebScraper()
                await global_scraper.__aenter__()
                logger.info("✅ Created new global scraper")
            except Exception as e:
                logger.error(f"❌ Failed to create scraper: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to initialize scraper"
                )
        
        return global_scraper

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Optimized Web Scraping Service is running",
        "version": "2.0.0",
        "status": "healthy",
        "config": RENDER_CONFIG
    }

# NEW: Streaming endpoint for real-time progress
@app.post("/scrape/stream")
async def scrape_websites_streaming(request: ScrapeRequest):
    """Stream scraping progress in real-time to prevent timeouts"""
    
    async def generate_progress():
        start_time = time.time()
        timeout_seconds = request.timeout_minutes * 60
        
        try:
            # Limit articles for free tier
            max_articles = min(
                request.max_articles_per_url or RENDER_CONFIG['MAX_ARTICLES_PER_BATCH'],
                RENDER_CONFIG['MAX_TOTAL_ARTICLES']
            )
            
            urls = [str(url) for url in request.base_urls]
            scraper = await get_scraper()
            
            # Send initial status
            yield f"data: {json.dumps({'status': 'started', 'urls': len(urls), 'max_articles': max_articles})}\n\n"
            
            # Process with timeout awareness
            results = {}
            total_articles = 0
            
            for i, url in enumerate(urls):
                if time.time() - start_time > timeout_seconds:
                    yield f"data: {json.dumps({'status': 'timeout', 'processed': i, 'total': len(urls)})}\n\n"
                    break
                
                try:
                    # Send progress update
                    yield f"data: {json.dumps({'status': 'processing', 'url': url, 'progress': f'{i+1}/{len(urls)}'})}\n\n"
                    
                    # Process single URL with limited articles
                    url_results = await scraper.scrape_single_site(
                        url=url,
                        max_articles=max_articles,
                        delay_range=request.delay_range
                    )
                    
                    results[url] = url_results
                    articles_count = len(url_results.get("articles", []))
                    total_articles += articles_count
                    
                    # Send progress update
                    yield f"data: {json.dumps({'status': 'completed_url', 'url': url, 'articles_found': articles_count})}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    yield f"data: {json.dumps({'status': 'error', 'url': url, 'error': str(e)})}\n\n"
            
            # Send final results
            final_response = {
                'status': 'completed',
                'results': results,
                'total_articles': total_articles,
                'processing_time': time.time() - start_time
            }
            yield f"data: {json.dumps(final_response)}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

# OPTIMIZED: Main scraping endpoint with batching
@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_websites_optimized(request: ScrapeRequest):
    """
    Optimized scraping with timeout handling and batching
    """
    start_time = time.time()
    timeout_seconds = request.timeout_minutes * 60
    
    try:
        logger.info(f"Starting optimized scrape job for {len(request.base_urls)} URLs")
        
        # Apply Render.com limits
        max_articles = min(
            request.max_articles_per_url or RENDER_CONFIG['MAX_ARTICLES_PER_BATCH'],
            RENDER_CONFIG['MAX_TOTAL_ARTICLES']
        )
        
        urls = [str(url) for url in request.base_urls]
        scraper = await get_scraper()
        
        # Process with timeout awareness and limited scope
        results = {}
        total_articles = 0
        
        for i, url in enumerate(urls):
            # Check timeout before processing each URL
            if time.time() - start_time > timeout_seconds - 30:  # Leave 30s buffer
                logger.warning(f"Approaching timeout, stopping after {i} URLs")
                break
            
            try:
                logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
                
                # Process single URL with limited articles
                url_results = await scraper.scrape_single_site(
                    url=url,
                    max_articles=max_articles,
                    delay_range=request.delay_range,
                    timeout_per_article=30  # 30 sec per article max
                )
                
                results[url] = url_results
                articles_count = len(url_results.get("articles", []))
                total_articles += articles_count
                
                logger.info(f"Completed URL {i+1}/{len(urls)}: found {articles_count} articles")
                
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                results[url] = {"error": str(e), "articles": []}
        
        processing_time = time.time() - start_time
        
        response_data = {
            "success": True,
            "message": f"Processed {len(results)} URLs, found {total_articles} articles in {processing_time:.1f}s",
            "data": results,
            "timestamp": datetime.now().isoformat(),
            "total_urls_processed": len(results),
            "total_articles_found": total_articles,
            "processing_time_seconds": processing_time
        }
        
        logger.info(f"Optimized scrape completed: {total_articles} articles in {processing_time:.1f}s")
        return ScrapeResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error during optimized scraping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping failed: {str(e)}"
        )

# NEW: Batch processing endpoint
@app.post("/scrape/batch")
async def scrape_batch(request: BatchScrapeRequest, background_tasks: BackgroundTasks):
    """Process large jobs in background with job tracking"""
    
    job_id = f"job_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Initialize job status
    active_jobs[job_id] = {
        "status": "started",
        "progress": {"urls_processed": 0, "total_urls": len(request.base_urls)},
        "results": {},
        "start_time": time.time()
    }
    
    # Start background processing
    background_tasks.add_task(process_batch_job, job_id, request)
    
    return {
        "job_id": job_id,
        "status": "started",
        "message": f"Batch job started for {len(request.base_urls)} URLs",
        "check_status_url": f"/scrape/status/{job_id}"
    }

async def process_batch_job(job_id: str, request: BatchScrapeRequest):
    """Background task to process batch job"""
    try:
        urls = [str(url) for url in request.base_urls]
        scraper = await get_scraper()
        
        # Process in batches
        batch_size = request.batch_size or RENDER_CONFIG['BATCH_SIZE']
        results = {}
        
        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            
            # Update job status
            active_jobs[job_id]["status"] = "processing"
            active_jobs[job_id]["progress"]["urls_processed"] = i
            
            # Process batch
            for url in batch_urls:
                try:
                    url_results = await scraper.scrape_single_site(
                        url=url,
                        max_articles=request.max_articles_per_url or RENDER_CONFIG['MAX_ARTICLES_PER_BATCH']
                    )
                    results[url] = url_results
                except Exception as e:
                    logger.error(f"Error in batch processing {url}: {e}")
                    results[url] = {"error": str(e), "articles": []}
            
            # Small delay between batches
            await asyncio.sleep(2)
        
        # Job completed
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["results"] = results
        active_jobs[job_id]["progress"]["urls_processed"] = len(urls)
        
    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)

@app.get("/scrape/status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of batch job"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = active_jobs[job_id]
    
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        results=job.get("results"),
        error=job.get("error")
    )

@app.get("/health")
async def health_check():
    """Enhanced health check"""
    browser_paths = [
        "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
        "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome"
    ]
    
    browser_status = "missing"
    browser_path = None
    
    for path in browser_paths:
        if os.path.exists(path):
            browser_status = "available"
            browser_path = path
            break
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Optimized Web Scraping Service",
        "version": "2.0.0",
        "browser_status": browser_status,
        "browser_path": browser_path,
        "active_jobs": len(active_jobs),
        "config": RENDER_CONFIG,
        "global_scraper_status": "initialized" if global_scraper else "not_initialized"
    }

# Cleanup old jobs periodically
@app.on_event("startup")
async def cleanup_old_jobs():
    """Clean up old job data periodically"""
    async def cleanup_task():
        while True:
            try:
                current_time = time.time()
                jobs_to_remove = []
                
                for job_id, job_data in active_jobs.items():
                    # Remove jobs older than 1 hour
                    if current_time - job_data.get("start_time", 0) > 3600:
                        jobs_to_remove.append(job_id)
                
                for job_id in jobs_to_remove:
                    del active_jobs[job_id]
                    logger.info(f"Cleaned up old job: {job_id}")
                
                # Sleep for 10 minutes before next cleanup
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(600)
    
    # Start cleanup task in background
    asyncio.create_task(cleanup_task())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
