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

class GenericWebScraper:
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
            # Semantic HTML
            "article a",
            "main a",
            ".content a",
            ".main a",
            
            # Common article/post classes
            ".article a",
            ".post a",
            ".news a",
            ".blog a",
            ".story a",
            ".article-item a",
            ".post-item a",
            ".news-item a",
            ".blog-item a",
            ".article-card a",
            ".post-card a",
            ".news-card a",
            ".blog-card a",
            ".article-link",
            ".post-link",
            ".news-link",
            ".blog-link",
            
            # Grid/list items
            ".item a",
            ".card a",
            ".tile a",
            ".box a",
            ".entry a",
            
            # Generic content areas
            ".feed a",
            ".list a",
            ".grid a",
            ".items a",
            ".entries a",
            
            # Links with article-like href patterns
            "a[href*='/article/']",
            "a[href*='/blog/']",
            "a[href*='/news/']",
            "a[href*='/post/']",
            "a[href*='/details/']",
            "a[href*='/referenzen/']",
            "a[href*='/read/']",
            "a[href*='/view/']",
            
            # Date patterns in href
            "a[href*='/2024/']",
            "a[href*='/2025/']",
            "a[href*='/2023/']",
            "a[href*='-2024-']",
            "a[href*='-2025-']",
            "a[href*='-2023-']",
            
            # Call-to-action links
            "a:contains('Read More')",
            "a:contains('Continue')",
            "a:contains('Full Story')",
            "a:contains('Learn More')",
            "a:contains('See More')",
            "a:contains('Details')",
            "a:contains('Continue reading')",
            "a:contains('Mehr erfahren')",
            
            # Heading links
            "h1 a",
            "h2 a",
            "h3 a",
            "h4 a",
            
            # Broad fallback
            "a[href$='.html']",
            "a[href*='/']"
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
        page.set_default_timeout(30000)
        # Block unnecessary resources for faster loading
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,css,woff,woff2,ttf}", lambda route: route.abort())
        return page

    async def random_delay(self, min_delay: float = 2, max_delay: float = 5):
        """Add random delay between requests"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def scroll_and_load_content(self, page: Page, max_scrolls: int = 5) -> None:
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
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            await element.click()
                            logger.info(f"Clicked load more button: {selector}")
                            load_more_clicked = True
                            await asyncio.sleep(3)
                            break
                except Exception as e:
                    logger.debug(f"Error clicking {selector}: {e}")
                    continue

            if not load_more_clicked:
                old_height = await page.evaluate("document.body.scrollHeight")
                await asyncio.sleep(2)
                new_height = await page.evaluate("document.body.scrollHeight")
                
                if old_height == new_height:
                    logger.info("Reached end of page, no more content to load")
                    break

        logger.info("Content loading process completed")

    def _is_likely_article_url(self, url: str, base_url: str) -> bool:
        """Generic article URL detection using multiple heuristics"""
        if not url or url.startswith('#') or 'javascript:' in url:
            return False

        url_lower = url.lower()
        parsed_url = urlparse(url)
        
        # Must be same domain
        try:
            parsed_base = urlparse(base_url)
            if parsed_url.netloc != parsed_base.netloc:
                return False
        except:
            return False

        # Universal excludes - definitely not articles
        definite_excludes = [
            r'/search', r'/login', r'/register', r'/signup', r'/contact$',
            r'/about$', r'/privacy', r'/terms', r'/cookie', r'/legal',
            r'/sitemap', r'/robots\.txt', r'/favicon', r'\.css', r'\.js',
            r'\.pdf', r'\.doc', r'\.zip', r'\.exe', r'/feed', r'/rss',
            r'/tag(?:s)?/$', r'/category/$', r'/author/$', r'/user/$',
            r'/wp-admin', r'/admin', r'/dashboard', r'/settings',
            r'#', r'mailto:', r'tel:', r'ftp:', r'/print',
            r'/downloads?(?:\.html?)?$', r'/newsletter(?:\.html?)?$',
            r'/fairs(?:\.html?)?$', r'/data-protection', r'/driving-directions',
            r'/safety-data-sheets', r'/datanorm-gaeb', r'/invitation-to-tender',
            r'/warning-placard', r'/helpful-forms', r'/technical-information(?:\.html?)?$',
            r'/download-brochures(?:\.html?)?$', r'/index\.html?$', r'/$', r'/en/?$'
        ]
        
        for pattern in definite_excludes:
            if re.search(pattern, url_lower):
                return False

        # Strong positive signals - very likely articles
        strong_signals = [
            r'/article/', r'/post/', r'/news/', r'/blog/', r'/story/',
            r'/read/', r'/view/', r'/details/', r'/full/', r'/referenzen/',
            r'/\d{4}/\d{2}/\d{2}/', r'/\d{4}/\d{2}/', r'/\d{4}/',
            r'-\d{4}-\d{2}-\d{2}', r'-\d{4}-\d{2}', r'-\d{4}',
            r'/projects?-of-the-month'
        ]
        
        for pattern in strong_signals:
            if re.search(pattern, url_lower):
                logger.debug(f"URL matches strong signal '{pattern}': {url}")
                return True

        # Medium signals - could be articles
        medium_signals = [
            r'\.html$', r'\.htm$', r'/\w+/\w+', r'/[^/]{10,}',
            r'/entry/', r'/item/', r'/content/', r'/page/',
        ]
        
        has_medium_signal = any(re.search(pattern, url_lower) for pattern in medium_signals)
        
        # Content keywords that suggest articles
        content_keywords = [
            'breaking', 'exclusive', 'report', 'analysis', 'interview',
            'feature', 'opinion', 'editorial', 'review', 'update',
            'announcement', 'launch', 'release', 'study', 'research',
            'restoration', 'designer', 'defense', 'tower', 'underfloor',
            'heating', 'kindergarten', 'vienna', 'france', 'tamasi',
            'banking', 'aegean', 'hotel', 'church', 'refurbishment',
            'dream', 'sustainable', 'living'
        ]
        
        has_content_keyword = any(keyword in url_lower for keyword in content_keywords)
        
        # URL structure analysis
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        # Skip very short URLs unless they have content keywords
        if len(path_parts) < 2 and not has_content_keyword:
            return False
            
        # Skip URLs with too many query parameters
        if len(parsed_url.query.split('&')) > 3:
            return False

        # Include if has medium signal OR content keyword
        result = has_medium_signal or has_content_keyword
        if result:
            logger.debug(f"Including URL as potential article: {url}")
        else:
            logger.debug(f"Excluding URL (no article signals): {url}")
        
        return result

    async def extract_article_links(self, page: Page, base_url: str) -> List[str]:
        """Extract all article links from the page"""
        logger.info(f"Extracting article links from {base_url}")
        article_links = set()

        # Get all links using JavaScript
        try:
            all_links = await page.evaluate("""
                () => {
                    const links = [];
                    const elements = document.querySelectorAll('a[href]');
                    elements.forEach(el => {
                        const href = el.href;
                        if (href && href !== window.location.href) {
                            links.push(href);
                        }
                    });
                    return [...new Set(links)]; // Remove duplicates
                }
            """)
            
            logger.info(f"Found {len(all_links)} total links on page")
            
            # Filter for likely articles
            for link in all_links:
                if self._is_likely_article_url(link, base_url):
                    article_links.add(link)
                    
        except Exception as e:
            logger.error(f"Error extracting JavaScript links: {e}")

        # Also try BeautifulSoup extraction as backup
        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            for selector in self.article_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        href = element.get('href')
                        if href:
                            absolute_url = urljoin(base_url, href)
                            if self._is_likely_article_url(absolute_url, base_url):
                                article_links.add(absolute_url)
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
                            
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {e}")

        filtered_links = list(article_links)
        logger.info(f"Found {len(filtered_links)} potential article links")
        return filtered_links

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry_retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def extract_article_content(self, page: Page, article_url: str) -> Dict[str, Any]:
        """Extract content from a single article page"""
        logger.info(f"Extracting content from: {article_url}")
        
        try:
            await page.goto(article_url, wait_until='networkidle')
            await asyncio.sleep(2)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Extract using multiple strategies
            title = self._extract_title_generic(soup)
            date = self._extract_date_generic(soup, article_url)
            content_text = self._extract_content_generic(soup)
            image_url = self._extract_image_generic(soup, article_url)

            # Content quality check
            if len(content_text.strip()) < 50:
                logger.debug(f"Content very short for {article_url}, might not be an article")

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

    def _extract_title_generic(self, soup: BeautifulSoup) -> str:
        """Extract article title using multiple methods"""
        title_methods = [
            lambda: soup.find('meta', property='og:title'),
            lambda: soup.find('meta', name='twitter:title'),
            lambda: soup.find('h1'),
            lambda: soup.find('h2'),
            lambda: soup.select_one('.title, .headline, .post-title, .article-title, .entry-title'),
            lambda: soup.find('title')
        ]

        for method in title_methods:
            try:
                element = method()
                if element:
                    title = element.get('content', '') or element.get_text(strip=True)
                    if title and len(title.strip()) > 5:
                        return title.strip()
            except:
                continue

        return "No title found"

    def _extract_date_generic(self, soup: BeautifulSoup, url: str) -> str:
        """Extract publication date using multiple methods"""
        date_methods = [
            lambda: soup.find('time', attrs={'datetime': True}),
            lambda: soup.find('meta', property='article:published_time'),
            lambda: soup.find('meta', name='pubdate'),
            lambda: soup.select_one('.date, .published, .post-date, .article-date, .timestamp'),
        ]

        for method in date_methods:
            try:
                element = method()
                if element:
                    date = element.get('datetime') or element.get('content') or element.get_text(strip=True)
                    if date:
                        return date.strip()
            except:
                continue

        # Try to extract date from URL
        date_patterns = [
            r'/(\d{4})/(\d{2})/(\d{2})/',
            r'/(\d{4})-(\d{2})-(\d{2})',
            r'/(\d{4})/(\d{2})/',
            r'/(\d{4})-(\d{2})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, url)
            if match:
                return '-'.join(match.groups())

        return ""

    def _extract_content_generic(self, soup: BeautifulSoup) -> str:
        """Extract main article content using multiple methods"""
        # Remove unwanted elements first
        for unwanted in soup.select('script, style, nav, header, footer, aside, .sidebar, .menu, .navigation, .comments, .advertisement, .ads'):
            unwanted.decompose()

        # Try multiple content extraction methods
        content_methods = [
            lambda: soup.find('div', class_=re.compile(r'content|article|post|entry|main', re.I)),
            lambda: soup.find('article'),
            lambda: soup.find('main'),
            lambda: soup.find('div', attrs={'role': 'main'}),
            lambda: soup.find('div', id=re.compile(r'content|article|post|entry|main', re.I)),
        ]

        for method in content_methods:
            try:
                element = method()
                if element:
                    # Get text from paragraphs and headings
                    text_elements = element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                    content = '\n'.join([elem.get_text(strip=True) for elem in text_elements if elem.get_text(strip=True)])
                    if len(content) > 100:
                        return content
            except:
                continue

        # Fallback: get all paragraphs from the page
        paragraphs = soup.find_all('p')
        if paragraphs:
            content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            if len(content) > 100:
                return content

        return "No content found"

    def _extract_image_generic(self, soup: BeautifulSoup, base_url: str) -> str:
        """Extract main article image"""
        image_methods = [
            lambda: soup.find('meta', property='og:image'),
            lambda: soup.find('meta', name='twitter:image'),
            lambda: soup.select_one('article img, .content img, .post img, .article img'),
            lambda: soup.find('img'),
        ]

        for method in image_methods:
            try:
                element = method()
                if element:
                    src = element.get('content') or element.get('src') or element.get('data-src')
                    if src:
                        return urljoin(base_url, src)
            except:
                continue

        return ""

    def _is_within_week_window(self, date_str: str, week_start: datetime, week_end: datetime) -> bool:
        """Check if article date is within the specified week window"""
        if not date_str:
            logger.debug(f"No date found, including article")
            return True

        try:
            pub_dt = dateparser.parse(date_str)
            if not pub_dt:
                logger.debug(f"Could not parse date '{date_str}', including article")
                return True

            if not pub_dt.tzinfo:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            else:
                pub_dt = pub_dt.astimezone(timezone.utc)

            is_within = week_start <= pub_dt < week_end
            logger.debug(f"Date '{date_str}' parsed as {pub_dt}, within window: {is_within}")
            return is_within
            
        except Exception as e:
            logger.debug(f"Date parse error for '{date_str}': {e}, including article")
            return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception))
    )
    async def scrape_single_site(
        self,
        url: str,
        max_articles: int = 20,
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
                    
                    # Add to seen URLs
                    seen_urls.add(article_url)

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
        max_articles_per_url: int = 20,  # FIXED: Using the correct parameter name
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
                    max_articles_per_url,  # FIXED: Using correct parameter name
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
