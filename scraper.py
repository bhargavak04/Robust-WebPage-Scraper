import asyncio
import logging
import random
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime
import json
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        self.load_more_selectors = [
            "button:contains('Load More')",
            "button:contains('Show More')",
            "button:contains('Load More Articles')",
            "a:contains('Load More')",
            "a:contains('Show More')",
            ".load-more",
            ".show-more",
            "[data-load-more]",
            ".pagination .next",
            ".pagination a[rel='next']",
            "button[aria-label*='load']",
            "button[aria-label*='more']"
        ]
        
        self.article_selectors = [
            "article a",
            ".article a",
            ".post a",
            ".blog-post a",
            ".news-item a",
            ".card a",
            "a[href*='/article/']",
            "a[href*='/blog/']",
            "a[href*='/news/']",
            "a[href*='/post/']",
            "a:contains('Read More')",
            "a:contains('Read more')",
            "a:contains('Details')",
            "a:contains('Continue reading')"
        ]
        
        # Add timeout and concurrency limits for Render.com
        self.page_timeout = 30000  # 30 seconds per page
        self.article_timeout = 20000  # 20 seconds per article
        self.max_concurrent_articles = 3  # Limit concurrent processing

    async def __aenter__(self):
        """Enhanced async context manager with better error handling"""
        try:
            self.playwright = await async_playwright().start()
            await self._ensure_browser_installed()
            
            # Simplified browser launch with most reliable method first
            self.browser = await self._launch_browser()
            logger.info("✅ Browser launched successfully")
            return self
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize WebScraper: {e}")
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            raise

    async def _launch_browser(self):
        """Simplified browser launch with better error handling"""
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor'
        ]
        
        # Try browser paths in order of reliability
        browser_paths = [
            None,  # Default path
            "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
            "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
            "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome"
        ]
        
        for i, path in enumerate(browser_paths):
            try:
                logger.info(f"Trying browser launch method {i+1}" + (f" with path: {path}" if path else ""))
                
                if path:
                    browser = await self.playwright.chromium.launch(
                        headless=True,
                        executable_path=path,
                        args=browser_args
                    )
                else:
                    browser = await self.playwright.chromium.launch(
                        headless=True,
                        args=browser_args
                    )
                
                # Test browser by creating a page
                test_context = await browser.new_context()
                test_page = await test_context.new_page()
                await test_page.close()
                await test_context.close()
                
                logger.info(f"✅ Browser launched successfully with method {i+1}")
                return browser
                
            except Exception as e:
                logger.error(f"❌ Browser launch method {i+1} failed: {e}")
                if 'browser' in locals():
                    try:
                        await browser.close()
                    except:
                        pass
                continue
        
        raise Exception("All browser launch methods failed")

    async def _ensure_browser_installed(self):
        """Optimized browser installation"""
        import subprocess
        import os
        
        # Check if browser exists
        browser_paths = [
            "/home/scraper/.cache/ms-playwright/chromium-1091/chrome-linux/chrome",
            "/app/.cache/ms-playwright/chromium-1091/chrome-linux/chrome"
        ]
        
        for path in browser_paths:
            if os.path.exists(path):
                logger.info(f"✅ Browser found at {path}")
                return
        
        logger.info("🔧 Installing Playwright browser...")
        try:
            result = subprocess.run(
                ["playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=180,
                env={**os.environ, "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "0"}
            )
            
            if result.returncode == 0:
                logger.info("✅ Browser installation successful")
            else:
                logger.warning(f"⚠️ Browser installation warning: {result.stderr}")
                
        except Exception as e:
            logger.error(f"❌ Browser installation failed: {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Enhanced cleanup"""
        try:
            if hasattr(self, 'browser'):
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            logger.info("✅ WebScraper cleaned up successfully")
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def create_page(self) -> Page:
        """Create a new browser page with optimized settings"""
        try:
            context = await self.browser.new_context(
                user_agent=random.choice(self.user_agents),
                viewport={'width': 1366, 'height': 768},  # Smaller viewport for performance
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            page = await context.new_page()
            
            # Set optimized timeouts
            page.set_default_timeout(self.page_timeout)
            
            # Block unnecessary resources for better performance
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,css,woff,woff2,ttf,mp4,mp3,pdf}", lambda route: route.abort())
            
            return page
            
        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            raise

    async def random_delay(self, min_delay: float = 1, max_delay: float = 3):
        """Optimized delay for faster processing"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def scroll_and_load_content(self, page: Page, max_scrolls: int = 5) -> None:
        """Optimized content loading with timeout protection"""
        logger.info("Starting optimized content loading...")
        
        try:
            for scroll_attempt in range(max_scrolls):
                # Quick scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)  # Reduced wait time
                
                # Try to find and click load more buttons
                load_more_clicked = False
                
                # Simplified load more detection
                load_more_buttons = await page.query_selector_all("button, a")
                
                for button in load_more_buttons[:5]:  # Limit to first 5 buttons
                    try:
                        text_content = await button.text_content()
                        if text_content and any(keyword in text_content.lower() for keyword in ['load more', 'show more', 'view more']):
                            is_visible = await button.is_visible()
                            if is_visible:
                                await button.click()
                                logger.info("Clicked load more button")
                                load_more_clicked = True
                                await asyncio.sleep(2)
                                break
                    except:
                        continue
                
                # Check if we've reached the end
                if not load_more_clicked:
                    old_height = await page.evaluate("document.body.scrollHeight")
                    await asyncio.sleep(1)
                    new_height = await page.evaluate("document.body.scrollHeight")
                    
                    if old_height == new_height:
                        logger.info("Reached end of page")
                        break
            
            logger.info("Content loading completed")
            
        except Exception as e:
            logger.error(f"Error during content loading: {e}")

    async def extract_article_links(self, page: Page, base_url: str) -> List[str]:
        """Enhanced article link extraction with better error handling"""
        logger.info(f"Extracting article links from {base_url}")
        
        article_links = set()
        
        try:
            # Get page content safely
            content = await page.content()
            if not content:
                logger.warning("No page content found")
                return []
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract links using various selectors
            for selector in self.article_selectors:
                try:
                    # Use CSS selectors that work with BeautifulSoup
                    css_selector = selector.replace(':contains(', '[').replace(')', ']') if ':contains(' in selector else selector
                    elements = soup.select(css_selector)
                    
                    for element in elements:
                        href = element.get('href')
                        if href:
                            absolute_url = urljoin(base_url, href)
                            if self._is_article_url(absolute_url, base_url):
                                article_links.add(absolute_url)
                                
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            # Also get links directly from the page
            try:
                js_links = await page.evaluate("""
                    () => {
                        const links = [];
                        const elements = document.querySelectorAll('a[href]');
                        elements.forEach(el => {
                            const href = el.href;
                            if (href && !href.includes('#') && !href.includes('javascript:')) {
                                links.push(href);
                            }
                        });
                        return links;
                    }
                """)
                
                for link in js_links:
                    if self._is_article_url(link, base_url):
                        article_links.add(link)
                        
            except Exception as e:
                logger.debug(f"Error extracting JS links: {e}")
            
            filtered_links = list(article_links)
            logger.info(f"Found {len(filtered_links)} article links")
            
            return filtered_links
            
        except Exception as e:
            logger.error(f"Error extracting article links: {e}")
            return []

    def _is_article_url(self, url: str, base_url: str) -> bool:
        """Enhanced URL filtering"""
        if not url or url.startswith('#') or 'javascript:' in url:
            return False
        
        # Skip common non-article URLs
        skip_patterns = [
            r'/(contact|about|privacy|terms|login|register|search)',
            r'\.(pdf|doc|xls|zip|mp4|mp3|jpg|png|gif)$',
            r'/(api|admin|wp-admin|wp-content)',
            r'mailto:',
            r'tel:'
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # Check for article patterns
        article_patterns = [
            r'/article/',
            r'/blog/',
            r'/news/',
            r'/post/',
            r'/story/',
            r'\.html',
            r'\d{4}/\d{2}/'
        ]
        
        for pattern in article_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        # Same domain check
        try:
            parsed_url = urlparse(url)
            parsed_base = urlparse(base_url)
            return parsed_url.netloc == parsed_base.netloc
        except:
            return False

    @retry(
        stop=stop_after_attempt(2),  # Reduced retries for speed
        wait=wait_exponential(multiplier=1, min=2, max=4),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def extract_article_content(self, page: Page, article_url: str) -> Dict[str, Any]:
        """Enhanced article content extraction with timeout protection"""
        logger.info(f"Extracting content from: {article_url}")
        
        start_time = time.time()
        
        try:
            # Set shorter timeout for individual articles
            page.set_default_timeout(self.article_timeout)
            
            # Navigate to article
            await page.goto(article_url, wait_until='domcontentloaded', timeout=self.article_timeout)
            
            # Quick wait for content
            await asyncio.sleep(1)
            
            # Get page content
            content = await page.content()
            if not content:
                raise Exception("No page content received")
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract data with safe methods
            title = self._safe_extract_title(soup)
            date = self._safe_extract_date(soup, article_url)
            content_text = self._safe_extract_content(soup)
            image_url = self._safe_extract_image(soup, article_url)
            
            processing_time = time.time() - start_time
            
            return {
                "title": title,
                "date": date,
                "content": content_text,
                "image": image_url,
                "url": article_url,
                "processing_time": round(processing_time, 2)
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {article_url}: {e}")
            return {
                "title": "Error extracting content",
                "date": "",
                "content": f"Error: {str(e)}",
                "image": "",
                "url": article_url,
                "processing_time": time.time() - start_time
            }

    def _safe_extract_title(self, soup: BeautifulSoup) -> str:
        """Safe title extraction with fallbacks"""
        title_selectors = [
            'h1',
            '.article-title',
            '.post-title',
            '.entry-title',
            '[property="og:title"]',
            'title'
        ]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    if title and len(title) > 5:
                        return title[:200]  # Limit title length
            except Exception:
                continue
        
        return "No title found"

    def _safe_extract_date(self, soup: BeautifulSoup, url: str) -> str:
        """Safe date extraction"""
        date_selectors = [
            'time[datetime]',
            '.article-date',
            '.post-date',
            '.published',
            '[property="article:published_time"]'
        ]
        
        for selector in date_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    date_attr = element.get('datetime')
                    if date_attr:
                        return date_attr[:20]  # Limit date length
                    
                    date_text = element.get_text(strip=True)
                    if date_text:
                        return date_text[:20]
            except Exception:
                continue
        
        # Try to extract from URL
        try:
            date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if date_match:
                year, month, day = date_match.groups()
                return f"{year}-{month}-{day}"
        except Exception:
            pass
        
        return ""

    def _safe_extract_content(self, soup: BeautifulSoup) -> str:
        """Safe content extraction"""
        content_selectors = [
            '.article-content',
            '.post-content',
            '.entry-content',
            'article',
            '.content'
        ]
        
        for selector in content_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    # Remove unwanted elements
                    for unwanted in element.select('script, style, nav, header, footer, .sidebar'):
                        unwanted.decompose()
                    
                    content = element.get_text(separator=' ', strip=True)
                    if content and len(content) > 50:
                        return content[:2000]  # Limit content length
            except Exception:
                continue
        
        # Fallback to paragraphs
        try:
            paragraphs = soup.find_all('p')
            if paragraphs:
                content = ' '.join([p.get_text(strip=True) for p in paragraphs[:10]])  # Limit to 10 paragraphs
                if content and len(content) > 50:
                    return content[:2000]
        except Exception:
            pass
        
        return "No content found"

    def _safe_extract_image(self, soup: BeautifulSoup, base_url: str) -> str:
        """Safe image extraction"""
        image_selectors = [
            '[property="og:image"]',
            '.article-image img',
            '.featured-image img',
            'article img'
        ]
        
        for selector in image_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    src = element.get('src') or element.get('data-src')
                    if src:
                        return urljoin(base_url, src)
            except Exception:
                continue
        
        return ""

    async def scrape_single_site(
        self, 
        url: str, 
        max_articles: int = 15, 
        delay_range: Tuple[float, float] = (1, 2),
        timeout_per_article: int = 30
    ) -> Dict[str, Any]:
        """Optimized single site scraping with timeout protection"""
        logger.info(f"Starting to scrape: {url}")
        
        start_time = time.time()
        page = None
        
        try:
            page = await self.create_page()
            
            # Navigate to main page
            await page.goto(url, wait_until='domcontentloaded', timeout=self.page_timeout)
            await asyncio.sleep(2)
            
            # Load content
            await self.scroll_and_load_content(page, max_scrolls=3)
            
            # Extract article links
            article_links = await self.extract_article_links(page, url)
            
            # Limit articles for performance
            max_articles = min(max_articles, 25)  # Hard limit for Render.com
            if len(article_links) > max_articles:
                article_links = article_links[:max_articles]
            
            logger.info(f"Found {len(article_links)} articles to process")
            
            # Process articles with timeout protection
            articles = []
            processing_start = time.time()
            max_processing_time = 180  # 3 minutes max for all articles
            
            for i, article_url in enumerate(article_links):
                # Check overall timeout
                if time.time() - processing_start > max_processing_time:
                    logger.warning(f"Overall timeout reached, stopping at article {i}")
                    break
                
                try:
                    logger.info(f"Processing article {i+1}/{len(article_links)}: {article_url}")
                    
                    article_content = await asyncio.wait_for(
                        self.extract_article_content(page, article_url),
                        timeout=timeout_per_article
                    )
                    
                    articles.append(article_content)
                    
                    # Quick delay between articles
                    await self.random_delay(*delay_range)
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout processing article: {article_url}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing article {article_url}: {e}")
                    continue
            
            processing_time = time.time() - start_time
            
            return {
                "base_url": url,
                "articles": articles,
                "total_articles_found": len(article_links),
                "successfully_processed": len(articles),
                "processing_time": round(processing_time, 2)
            }
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "base_url": url,
                "articles": [],
                "error": str(e),
                "total_articles_found": 0,
                "successfully_processed": 0,
                "processing_time": time.time() - start_time
            }
        finally:
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.error(f"Error closing page: {e}")

    async def scrape_multiple_sites(
        self,
        urls: List[str],
        max_articles_per_url: int = 15,
        delay_range: Tuple[float, float] = (1, 2)
    ) -> Dict[str, Any]:
        """Optimized multiple site scraping"""
        logger.info(f"Starting to scrape {len(urls)} websites")
        
        results = {}
        
        # Process URLs with timeout protection
        for i, url in enumerate(urls):
            try:
                logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
                
                # Process with timeout
                result = await asyncio.wait_for(
                    self.scrape_single_site(url, max_articles_per_url, delay_range),
                    timeout=240  # 4 minutes per URL
                )
                
                results[url] = result
                
                # Delay between URLs
                if i < len(urls) - 1:
                    await self.random_delay(*delay_range)
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout processing URL: {url}")
                results[url] = {
                    "base_url": url,
                    "articles": [],
                    "error": "Timeout error",
                    "total_articles_found": 0,
                    "successfully_processed": 0
                }
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                results[url] = {
                    "base_url": url,
                    "articles": [],
                    "error": str(e),
                    "total_articles_found": 0,
                    "successfully_processed": 0
                }
        
        logger.info(f"Completed scraping {len(urls)} websites")
        return results
