import os
import json
import logging
import random
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import uvicorn

from scraper import WebScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Robust Web Scraping Service",
    description="A production-grade web scraping service for extracting news and blog content",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No authentication required for simplicity

# Pydantic models
class ScrapeRequest(BaseModel):
    base_urls: List[HttpUrl]
    max_articles_per_url: Optional[int] = 50
    delay_range: Optional[tuple] = (2, 5)

class ScrapeResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]
    timestamp: str
    total_urls_processed: int
    total_articles_found: int

# Initialize scraper (will be created per request)
scraper = None

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Robust Web Scraping Service is running",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_websites(request: ScrapeRequest):
    """
    Scrape multiple websites for news and blog content.
    
    Args:
        request: ScrapeRequest containing list of URLs to scrape
    
    Returns:
        ScrapeResponse with scraped data and metadata
    """
    try:
        
        logger.info(f"Starting scrape job for {len(request.base_urls)} URLs")
        
        # Convert URLs to strings
        urls = [str(url) for url in request.base_urls]
        
        # Scrape all URLs
        async with WebScraper() as scraper:
            results = await scraper.scrape_multiple_sites(
                urls=urls,
                max_articles_per_url=request.max_articles_per_url,
                delay_range=request.delay_range
            )
        
        # Calculate statistics
        total_urls_processed = len(results)
        total_articles_found = sum(
            len(result.get("articles", [])) for result in results.values()
        )
        
        response_data = {
            "success": True,
            "message": f"Successfully scraped {total_urls_processed} URLs, found {total_articles_found} articles",
            "data": results,
            "timestamp": datetime.now().isoformat(),
            "total_urls_processed": total_urls_processed,
            "total_articles_found": total_articles_found
        }
        
        logger.info(f"Scrape job completed successfully. Found {total_articles_found} articles across {total_urls_processed} URLs")
        
        return ScrapeResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Robust Web Scraping Service",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
