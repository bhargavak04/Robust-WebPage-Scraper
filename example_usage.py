#!/usr/bin/env python3
"""
Example usage of the Robust Web Scraping Service API
"""

import requests
import json

def main():
    # API endpoint (change this to your deployed service URL)
    API_BASE_URL = "http://localhost:8000"
    
    print("🚀 Starting scraping request...")
    print()
    
    # Example URLs to scrape
    urls_to_scrape = [
        "https://www.variotherm.com/en/service/news/projects-of-the-month.html",
        # Add more URLs here
    ]
    
    # Prepare the request
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "base_urls": urls_to_scrape,
        "max_articles_per_url": 10,  # Limit to 10 articles per URL for testing
        "delay_range": [2, 4]  # 2-4 second delays between requests
    }
    
    print("📡 Sending scraping request...")
    print(f"URLs to scrape: {len(urls_to_scrape)}")
    print(f"Max articles per URL: {payload['max_articles_per_url']}")
    print()
    
    try:
        # Make the API request
        response = requests.post(
            f"{API_BASE_URL}/scrape",
            headers=headers,
            json=payload,
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("✅ Scraping completed successfully!")
            print(f"Message: {result['message']}")
            print(f"Total URLs processed: {result['total_urls_processed']}")
            print(f"Total articles found: {result['total_articles_found']}")
            print(f"Timestamp: {result['timestamp']}")
            print()
            
            # Display results for each site
            for site_key, site_data in result['data'].items():
                print(f"🌐 {site_data['base_url']}")
                print(f"   Articles found: {site_data['total_articles_found']}")
                print(f"   Successfully processed: {site_data['successfully_processed']}")
                
                if site_data.get('error'):
                    print(f"   ❌ Error: {site_data['error']}")
                else:
                    # Show first article as example
                    if site_data['articles']:
                        first_article = site_data['articles'][0]
                        print(f"   📄 Sample article:")
                        print(f"      Title: {first_article['title'][:60]}...")
                        print(f"      Date: {first_article['date']}")
                        print(f"      URL: {first_article['url']}")
                        print(f"      Content length: {len(first_article['content'])} chars")
                        if first_article['image']:
                            print(f"      Image: {first_article['image']}")
                print()
            
            # Save results to file
            with open('scraping_results.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("💾 Results saved to scraping_results.json")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out. The scraping process may take several minutes.")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error. Make sure the service is running.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_health_check():
    """Test the health check endpoint"""
    API_BASE_URL = "http://localhost:8000"
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            health_data = response.json()
            print("🏥 Health check passed!")
            print(f"Status: {health_data['status']}")
            print(f"Service: {health_data['service']}")
            print(f"Version: {health_data['version']}")
            print(f"Timestamp: {health_data['timestamp']}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

if __name__ == "__main__":
    print("🚀 Robust Web Scraping Service - Example Usage")
    print("=" * 50)
    
    # Test health check first
    print("Testing health check...")
    test_health_check()
    print()
    
    # Run the main example
    main()
