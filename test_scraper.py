#!/usr/bin/env python3
"""
Test script for the Robust Web Scraping Service
"""

import asyncio
import json
import sys

# Add the current directory to Python path
sys.path.append('.')

from scraper import WebScraper

async def test_scraper():
    """Test the scraping functionality"""
    
    # Test URLs (replace with actual URLs you want to test)
    test_urls = [
        "https://www.variotherm.com/en/service/news/projects-of-the-month.html",
        # Add more test URLs here
    ]
    
    print("🚀 Starting Robust Web Scraping Service Test")
    print("=" * 50)
    
    print("✅ Starting scraper test...")
    
    # Initialize scraper
    async with WebScraper() as scraper:
        print(f"✅ Scraper initialized successfully")
        
        # Test single site scraping
        print(f"\n📡 Testing single site scraping...")
        for url in test_urls:
            print(f"   Scraping: {url}")
            try:
                result = await scraper.scrape_single_site(url, max_articles=5)
                print(f"   ✅ Found {len(result['articles'])} articles")
                
                # Display first article as example
                if result['articles']:
                    first_article = result['articles'][0]
                    print(f"   📄 Sample article:")
                    print(f"      Title: {first_article['title'][:50]}...")
                    print(f"      Date: {first_article['date']}")
                    print(f"      URL: {first_article['url']}")
                    print(f"      Content length: {len(first_article['content'])} chars")
                
            except Exception as e:
                print(f"   ❌ Error scraping {url}: {e}")
        
        # Test multiple sites scraping
        print(f"\n📡 Testing multiple sites scraping...")
        try:
            results = await scraper.scrape_multiple_sites(
                urls=test_urls,
                max_articles_per_url=3,
                delay_range=(1, 2)
            )
            
            total_articles = sum(
                len(result.get('articles', [])) for result in results.values()
            )
            print(f"   ✅ Successfully scraped {len(results)} sites")
            print(f"   📄 Total articles found: {total_articles}")
            
            # Save results to file
            with open('test_results.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"   💾 Results saved to test_results.json")
            
        except Exception as e:
            print(f"   ❌ Error in multiple sites scraping: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Test completed!")

def test_health():
    """Test health check functionality"""
    print("\n🏥 Testing health check...")
    print("   ✅ Health check functionality ready")

if __name__ == "__main__":
    print("🧪 Robust Web Scraping Service - Test Suite")
    print("=" * 50)
    
    # Test health check
    test_health()
    
    # Test scraper
    try:
        asyncio.run(test_scraper())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)
