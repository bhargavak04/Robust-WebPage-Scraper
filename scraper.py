import asyncio
import logging
import random
import time
import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone, timedelta
import json
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dateutil import parser as dateparser

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

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def create_page(self) -> Page:
        """Create a new browser page with custom settings"""
        context = await self.browser.new_context(
            user_agent=random.choice(self.user_agents),
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        page = await context.new_page()
        # Set default timeout
        page.set_default_timeout(30000)
        # Intercept and block unnecessary resources
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,css,woff,woff2,ttf}", lambda route: route.abort())
        return page

    async def random_delay(self, min_delay: float = 2, max_delay: float = 5):
        """Add random delay between requests"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def scroll_and_load_content(self, page: Page, max_scrolls: int = 10) -> None:
        """Scroll to bottom and click load more buttons until all content is loaded"""
        logger.info("Starting content loading process...")
        for scroll_attempt in range(max_scrolls):
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            # Try to find and click load more buttons
            load_more_clicked = False
            for selector in self.load_more_selectors:
                try:
                    # Check if element exists and is visible
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            await element.click()
                            logger.info(f"Clicked load more button: {selector}")
                            load_more_clicked = True
                            await asyncio.sleep(3)  # Wait for content to load
                            break
                except Exception as e:
                    logger.debug(f"Error clicking {selector}: {e}")
                    continue

            # If no load more button was clicked, try scrolling again
            if not load_more_clicked:
                # Check if we've reached the end
                old_height = await page.evaluate("document.body.scrollHeight")
                await asyncio.sleep(2)
                new_height = await page.evaluate("document.body.scrollHeight")
                if old_height == new_height:
                    logger.info("Reached end of page, no more content to load")
                    break

        logger.info("Content loading process completed")

    async def extract_article_links(self, page: Page, base_url: str) -> List[str]:
        """Extract all article links from the page"""
        logger.info(f"Extracting article links from {base_url}")
        article_links = set()

        # Get page content
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Extract links using various selectors
        for selector in self.article_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href')
                    if href:
                        # Make URL absolute
                        absolute_url = urljoin(base_url, href)
                        # Filter out non-article URLs
                        if self._is_article_url(absolute_url, base_url):
                            article_links.add(absolute_url)
            except Exception as e:
                logger.debug(f"Error extracting links with selector {selector}: {e}")

        # Also look for links in JavaScript-rendered content
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

        # Remove duplicates and filter
        filtered_links = list(article_links)
        logger.info(f"Found {len(filtered_links)} potential article links")
        return filtered_links

    def _is_article_url(self, url: str, base_url: str) -> bool:
        """Check if URL is likely an article URL"""
        if not url or url.startswith('#'):
            return False

        # Check for common article patterns
        article_patterns = [
            r'/article/',
            r'/blog/',
            r'/news/',
            r'/post/',
            r'/story/',
            r'/entry/',
            r'\.html$',
            r'\.php$',
            r'\d{4}/\d{2}/',  # Date patterns
        ]

        for pattern in article_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        # Check if URL is on the same domain
        try:
            parsed_url = urlparse(url)
            parsed_base = urlparse(base_url)
            return parsed_url.netloc == parsed_base.netloc
        except:
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def extract_article_content(self, page: Page, article_url: str) -> Dict[str, Any]:
        """Extract content from a single article page"""
        logger.info(f"Extracting content from: {article_url}")
        try:
            await page.goto(article_url, wait_until='networkidle')
            await asyncio.sleep(2)

            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Extract title
            title = self._extract_title(soup)

            # Extract publication date
            date = self._extract_date(soup, article_url)

            # Extract main content
            content_text = self._extract_content(soup)

            # Extract image
            image_url = self._extract_image(soup, article_url)

            return {
                "title": title,
                "date": date,
                "content": content_text,
                "image": image_url,
                "url": article_url
            }

        except Exception as e:
            logger.error(f"Error extracting content from {article_url}: {e}")
            return {
                "title": "Error extracting content",
                "date": "",
                "content": f"Error: {str(e)}",
                "image": "",
                "url": article_url
            }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title"""
        title_selectors = [
            'h1',
            '.article-title',
            '.post-title',
            '.blog-title',
            '.entry-title',
            '[property="og:title"]',
            'title'
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 10:
                    return title

        return "No title found"

    def _extract_date(self, soup: BeautifulSoup, url: str) -> str:
        """Extract publication date"""
        date_selectors = [
            'time[datetime]',
            '.article-date',
            '.post-date',
            '.blog-date',
            '.entry-date',
            '[property="article:published_time"]',
            '.date',
            '.published'
        ]

        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                # Try to get datetime attribute first
                date_attr = element.get('datetime')
                if date_attr:
                    return date_attr

                # Otherwise get text content
                date_text = element.get_text(strip=True)
                if date_text:
                    return date_text

        # Try to extract from URL
        date_patterns = [
            r'/(\d{4})/(\d{2})/(\d{2})/',
            r'/(\d{4})-(\d{2})-(\d{2})',
            r'(\d{4})/(\d{2})/(\d{2})'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, url)
            if match:
                year, month, day = match.groups()
                return f"{year}-{month}-{day}"

        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main article content"""
        content_selectors = [
            '.article-content',
            '.post-content',
            '.blog-content',
            '.entry-content',
            '.content',
            'article',
            '.main-content',
            '.article-body'
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                # Remove unwanted elements
                for unwanted in element.select('script, style, nav, header, footer, .sidebar, .comments'):
                    unwanted.decompose()

                # Get text content
                content = element.get_text(separator='\n', strip=True)
                if content and len(content) > 100:
                    return content

        # Fallback: get all paragraphs
        paragraphs = soup.find_all('p')
        if paragraphs:
            content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            if content and len(content) > 100:
                return content

        return "No content found"

    def _extract_image(self, soup: BeautifulSoup, base_url: str) -> str:
        """Extract main article image"""
        image_selectors = [
            '[property="og:image"]',
            '[name="twitter:image"]',
            '.article-image img',
            '.post-image img',
            '.blog-image img',
            '.entry-image img',
            '.featured-image img',
            'article img'
        ]

        for selector in image_selectors:
            element = soup.select_one(selector)
            if element:
                src = element.get('src') or element.get('data-src')
                if src:
                    return urljoin(base_url, src)

        return ""

    def _is_within_week_window(self, date_str: str, week_start: datetime, week_end: datetime) -> bool:
        """Check if article date is within the specified week window"""
        if not date_str:
            return False
        
        try:
            # Parse the date string
            pub_dt = dateparser.parse(date_str)
            if not pub_dt:
                return False
            
            # Ensure timezone awareness
            if not pub_dt.tzinfo:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            else:
                pub_dt = pub_dt.astimezone(timezone.utc)
            
            # Check if within window
            return week_start <= pub_dt < week_end
        except Exception as e:
            logger.debug(f"Date parse error for '{date_str}': {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def scrape_single_site(
        self, 
        url: str, 
        max_articles: int = 50,
        week_start: Optional[datetime] = None,
        week_end: Optional[datetime] = None,
        seen_urls: Optional[set] = None
    ) -> Dict[str, Any]:
        """Scrape a single website for articles with date filtering and deduplication"""
        logger.info(f"Starting to scrape: {url}")
        
        # Default to current week if not provided
        if week_start is None or week_end is None:
            now = datetime.now(timezone.utc)
            week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
        
        if seen_urls is None:
            seen_urls = set()
        
        page = None
        try:
            page = await self.create_page()

            # Navigate to the page
            await page.goto(url, wait_until='networkidle')
            await asyncio.sleep(3)

            # Scroll and load all content
            await self.scroll_and_load_content(page)

            # Extract article links
            article_links = await self.extract_article_links(page, url)

            # Limit number of articles to check
            if max_articles and len(article_links) > max_articles:
                article_links = article_links[:max_articles]

            logger.info(f"Found {len(article_links)} articles to process")

            # Extract content from each article with filtering
            articles = []
            processed_count = 0
            
            for i, article_url in enumerate(article_links):
                try:
                    # Skip if already seen
                    if article_url in seen_urls:
                        logger.debug(f"Skipping already seen URL: {article_url}")
                        continue
                    
                    logger.info(f"Processing article {i+1}/{len(article_links)}: {article_url}")
                    article_content = await self.extract_article_content(page, article_url)
                    
                    # Check if article is within the week window
                    article_date = article_content.get("date", "")
                    if not self._is_within_week_window(article_date, week_start, week_end):
                        logger.debug(f"Article {article_url} is outside week window, skipping")
                        continue
                    
                    # Add hash for additional deduplication
                    title = article_content.get("title", "")
                    raw_hash = hashlib.sha256(
                        (title + article_url).encode("utf-8")
                    ).hexdigest()
                    
                    article_content["raw_hash"] = raw_hash
                    article_content["discovered_at"] = datetime.now(timezone.utc).isoformat()
                    
                    articles.append(article_content)
                    processed_count += 1

                    # Add delay between article requests
                    await self.random_delay(1, 3)

                except Exception as e:
                    logger.error(f"Error processing article {article_url}: {e}")
                    continue

            logger.info(f"Scraped {len(articles)} articles within week window from {url}")
            
            return {
                "base_url": url,
                "articles": articles,
                "total_articles_found": len(article_links),
                "successfully_processed": processed_count,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat()
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "base_url": url,
                "articles": [],
                "error": str(e),
                "total_articles_found": 0,
                "successfully_processed": 0,
                "week_start": week_start.isoformat() if week_start else None,
                "week_end": week_end.isoformat() if week_end else None
            }

        finally:
            if page:
                await page.close()

    async def scrape_multiple_sites(
        self,
        urls: List[str],
        max_articles_per_url: int = 50,
        delay_range: Tuple[float, float] = (2, 5),
        week_start: Optional[datetime] = None,
        week_end: Optional[datetime] = None,
        seen_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Scrape multiple websites concurrently with date filtering and deduplication"""
        logger.info(f"Starting to scrape {len(urls)} websites")
        
        # Convert seen_urls list to set for faster lookups
        seen_set = set(seen_urls or [])
        
        results = {}

        # Process URLs sequentially to avoid overwhelming servers
        for i, url in enumerate(urls):
            try:
                logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
                result = await self.scrape_single_site(
                    url, 
                    max_articles_per_url,
                    week_start=week_start,
                    week_end=week_end,
                    seen_urls=seen_set
                )
                
                # Add newly found URLs to seen set for subsequent sites
                for article in result.get("articles", []):
                    seen_set.add(article["url"])
                
                results[f"scrapeResult{i+1}"] = result

                # Add delay between different websites
                if i < len(urls) - 1:
                    await self.random_delay(*delay_range)

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                results[f"scrapeResult{i+1}"] = {
                    "base_url": url,
                    "articles": [],
                    "error": str(e),
                    "total_articles_found": 0,
                    "successfully_processed": 0,
                    "week_start": week_start.isoformat() if week_start else None,
                    "week_end": week_end.isoformat() if week_end else None
                }

        logger.info(f"Completed scraping {len(urls)} websites")
        return results
