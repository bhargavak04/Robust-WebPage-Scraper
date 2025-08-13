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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
        ]

        self.load_more_selectors = [
            "button:contains('Load More')", "button:contains('Show More')", "button:contains('More')",
            "a:contains('Load More')", "a:contains('Show More')", "a:contains('More')",
            ".load-more", ".show-more", ".more-button", ".load-button",
            "[data-load-more]", "[data-show-more]", "[data-more]",
            ".pagination .next", ".pagination a[rel='next']", ".next-page"
        ]

        self.article_selectors = [
            "article a", "main a", ".content a", ".main a",
            ".article a", ".post a", ".news a", ".blog a", ".story a",
            ".article-item a", ".post-item a", ".news-item a", ".blog-item a",
            ".article-card a", ".post-card a", ".news-card a", ".blog-card a",
            ".item a", ".card a", ".tile a", ".box a", ".entry a",
            "a[href*='/article']", "a[href*='/post']", "a[href*='/news']", 
            "a[href*='/blog']", "a[href*='/story']", "a[href*='/details']",
            "a[href*='/2024/']", "a[href*='/2025/']", "a[href*='/2023/']",
            "a:contains('Read More')", "a:contains('Continue')", "a:contains('Details')",
            "h1 a", "h2 a", "h3 a", "h4 a",
            "a[href$='.html']"
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

    async def create_page(self) -> Page:
        context = await self.browser.new_context(
            user_agent=random.choice(self.user_agents),
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        page.set_default_timeout(30000)
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,css,woff,woff2,ttf}", lambda route: route.abort())
        return page

    async def scroll_and_load_content(self, page: Page, max_scrolls: int = 3) -> None:
        logger.info("Starting content loading process...")
        
        for scroll_attempt in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            load_more_clicked = False
            for selector in self.load_more_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info(f"Clicked load more button: {selector}")
                        load_more_clicked = True
                        await asyncio.sleep(3)
                        break
                except:
                    continue

            if not load_more_clicked:
                old_height = await page.evaluate("document.body.scrollHeight")
                await asyncio.sleep(2)
                new_height = await page.evaluate("document.body.scrollHeight")
                if old_height == new_height:
                    break

        logger.info("Content loading process completed")

    def _is_likely_article_url(self, url: str, base_url: str) -> bool:
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

        # Universal excludes
        definite_excludes = [
            r'/search', r'/login', r'/register', r'/contact', r'/about', 
            r'/privacy', r'/terms', r'/cookie', r'/legal', r'/sitemap',
            r'\.css', r'\.js', r'\.pdf', r'\.doc', r'\.zip', 
            r'/feed', r'/rss', r'/tag(?:s)?/', r'/category/', 
            r'/author/', r'/user/', r'/admin', r'#', r'mailto:', r'tel:'
        ]
        
        for pattern in definite_excludes:
            if re.search(pattern, url_lower):
                return False

        # Strong positive signals
        strong_signals = [
            r'/article/', r'/post/', r'/news/', r'/blog/', r'/story/',
            r'/read/', r'/view/', r'/details/', r'/full/',
            r'/\d{4}/\d{2}/\d{2}/', r'/\d{4}/\d{2}/', r'/\d{4}/',
            r'-\d{4}-\d{2}-\d{2}', r'-\d{4}-\d{2}', r'-\d{4}',
        ]
        
        for pattern in strong_signals:
            if re.search(pattern, url_lower):
                return True

        # Medium signals
        medium_signals = [
            r'\.html$', r'\.htm$', r'/\w+/\w+', r'/[^/]{10,}',
            r'/entry/', r'/item/', r'/content/', r'/page/',
        ]
        
        has_medium_signal = any(re.search(pattern, url_lower) for pattern in medium_signals)
        
        # Content keywords
        content_keywords = [
            'breaking', 'exclusive', 'report', 'analysis', 'interview',
            'feature', 'opinion', 'editorial', 'review', 'update',
            'announcement', 'launch', 'release', 'study', 'research'
        ]
        
        has_content_keyword = any(keyword in url_lower for keyword in content_keywords)
        
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        if len(path_parts) < 2 and not has_content_keyword:
            return False
            
        if len(parsed_url.query.split('&')) > 3:
            return False

        return has_medium_signal or has_content_keyword

    async def extract_article_links(self, page: Page, base_url: str) -> List[str]:
        logger.info(f"Extracting article links from {base_url}")
        article_links = set()

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
                    return [...new Set(links)];
                }
            """)
            
            for link in all_links:
                if self._is_likely_article_url(link, base_url):
                    article_links.add(link)
                    
        except Exception as e:
            logger.error(f"Error extracting links: {e}")

        try:
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            for selector in self.article_selectors[:10]:
                elements = soup.select(selector)
                for element in elements[:50]:
                    href = element.get('href')
                    if href:
                        absolute_url = urljoin(base_url, href)
                        if self._is_likely_article_url(absolute_url, base_url):
                            article_links.add(absolute_url)
                            
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {e}")

        filtered_links = list(article_links)
        logger.info(f"Found {len(filtered_links)} potential article links")
        return filtered_links

    async def extract_article_content(self, page: Page, article_url: str) -> Dict[str, Any]:
        logger.info(f"Extracting content from: {article_url}")
        
        try:
            await page.goto(article_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(1)

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            title = self._extract_title_generic(soup)
            date = self._extract_date_generic(soup, article_url)
            content_text = self._extract_content_generic(soup)
            image_url = self._extract_image_generic(soup, article_url)

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
        title_methods = [
            lambda: soup.find('meta', property='og:title'),
            lambda: soup.find('meta', name='twitter:title'),
            lambda: soup.find('h1'),
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

        # Extract date from URL
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
        # Remove unwanted elements
        for unwanted in soup.select('script, style, nav, header, footer, aside, .sidebar, .menu, .navigation, .comments, .ads'):
            unwanted.decompose()

        content_methods = [
            lambda: soup.find('div', class_=re.compile(r'content|article|post|entry|main', re.I)),
            lambda: soup.find('article'),
            lambda: soup.find('main'),
            lambda: soup.find('div', attrs={'role': 'main'}),
        ]

        for method in content_methods:
            try:
                element = method()
                if element:
                    text_elements = element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                    content = '\n'.join([elem.get_text(strip=True) for elem in text_elements if elem.get_text(strip=True)])
                    if len(content) > 100:
                        return content
            except:
                continue

        # Fallback
        paragraphs = soup.find_all('p')
        if paragraphs:
            content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            if len(content) > 100:
                return content

        return "No content found"

    def _extract_image_generic(self, soup: BeautifulSoup, base_url: str) -> str:
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

    def _is_within_time_window(self, date_str: str, days_back: int = 7) -> bool:
        if not date_str:
            return True

        try:
            pub_dt = dateparser.parse(date_str)
            if not pub_dt:
                return True

            if not pub_dt.tzinfo:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            else:
                pub_dt = pub_dt.astimezone(timezone.utc)

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            return pub_dt >= cutoff_date
            
        except Exception as e:
            logger.debug(f"Date parse error for '{date_str}': {e}")
            return True

    async def scrape_single_site(
        self,
        url: str,
        max_articles: int = 10,
        days_back: int = 7,
        seen_urls: Optional[set] = None
    ) -> Dict[str, Any]:
        logger.info(f"Starting to scrape: {url}")

        if seen_urls is None:
            seen_urls = set()

        page = None
        try:
            page = await self.create_page()
            await page.goto(url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

            await self.scroll_and_load_content(page)
            article_links = await self.extract_article_links(page, url)

            if max_articles:
                article_links = article_links[:max_articles]

            logger.info(f"Processing {len(article_links)} article links")

            articles = []
            for i, article_url in enumerate(article_links):
                if article_url in seen_urls:
                    continue

                logger.info(f"Processing article {i+1}/{len(article_links)}: {article_url}")
                
                article_content = await self.extract_article_content(page, article_url)
                
                if not self._is_within_time_window(article_content.get("date", ""), days_back):
                    continue

                article_content["raw_hash"] = hashlib.sha256(
                    (article_content.get("title", "") + article_url).encode("utf-8")
                ).hexdigest()
                article_content["discovered_at"] = datetime.now(timezone.utc).isoformat()
                
                articles.append(article_content)
                seen_urls.add(article_url)

                await asyncio.sleep(random.uniform(1, 3))

            logger.info(f"Successfully scraped {len(articles)} articles from {url}")
            
            return {
                "base_url": url,
                "articles": articles,
                "total_links_found": len(article_links),
                "articles_processed": len(articles)
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "base_url": url,
                "articles": [],
                "error": str(e),
                "total_links_found": 0,
                "articles_processed": 0
            }

        finally:
            if page:
                await page.close()

    async def scrape_multiple_sites(
        self,
        urls: List[str],
        max_articles_per_site: int = 10,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Main method called by your existing API"""
        logger.info(f"Starting to scrape {len(urls)} websites")

        seen_urls = set()
        results = {}

        for i, url in enumerate(urls):
            try:
                logger.info(f"Processing site {i+1}/{len(urls)}: {url}")
                
                result = await self.scrape_single_site(
                    url, max_articles_per_site, days_back, seen_urls
                )
                
                results[f"scrapeResult{i+1}"] = result
                
                if i < len(urls) - 1:
                    await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                results[f"scrapeResult{i+1}"] = {
                    "base_url": url,
                    "articles": [],
                    "error": str(e)
                }

        return results
