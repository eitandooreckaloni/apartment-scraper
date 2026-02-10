"""Facebook group scraper using Playwright."""

import asyncio
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..config import config

logger = structlog.get_logger()


@dataclass
class RawPost:
    """Raw post data extracted from Facebook."""
    post_id: str
    content: str
    author_name: Optional[str]
    post_url: str
    images: list[str]
    posted_at: Optional[datetime]
    group_name: str
    group_url: str


class FacebookScraper:
    """Scrapes apartment listings from Facebook groups."""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._logged_in = False
    
    async def _random_delay(self, min_sec: Optional[int] = None, max_sec: Optional[int] = None):
        """Wait a random amount of time to appear more human."""
        min_sec = min_sec or config.scraper_min_delay
        max_sec = max_sec or config.scraper_max_delay
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def start(self):
        """Start the browser and load session if available."""
        logger.info("Starting Facebook scraper")
        
        playwright = await async_playwright().start()
        
        # Use Firefox - less likely to be detected than Chromium
        self.browser = await playwright.firefox.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Try to load existing session
        session_path = config.session_path / "facebook_session.json"
        storage_state = None
        
        if session_path.exists():
            logger.info("Loading existing session")
            try:
                storage_state = str(session_path)
            except Exception as e:
                logger.warning("Failed to load session", error=str(e))
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="he-IL",
            timezone_id="Asia/Jerusalem"
        )
        
        self.page = await self.context.new_page()
        
        # Check if we're logged in
        await self._check_login_status()
    
    async def _check_login_status(self) -> bool:
        """Check if we're logged into Facebook."""
        try:
            await self.page.goto("https://www.facebook.com", wait_until="networkidle")
            await self._random_delay(2, 4)
            
            # Check for login form or user menu
            login_form = await self.page.query_selector('input[name="email"]')
            if login_form:
                self._logged_in = False
                logger.info("Not logged in - need to authenticate")
                return False
            
            self._logged_in = True
            logger.info("Already logged in")
            return True
            
        except Exception as e:
            logger.error("Error checking login status", error=str(e))
            return False
    
    async def login(self) -> bool:
        """Log into Facebook."""
        if self._logged_in:
            return True
        
        logger.info("Logging into Facebook")
        
        try:
            await self.page.goto("https://www.facebook.com/login", wait_until="networkidle")
            await self._random_delay()
            
            # Fill email
            await self.page.fill('input[name="email"]', config.fb_email)
            await self._random_delay(1, 2)
            
            # Fill password
            await self.page.fill('input[name="pass"]', config.fb_password)
            await self._random_delay(1, 2)
            
            # Click login button
            await self.page.click('button[name="login"]')
            
            # Wait for navigation
            await self.page.wait_for_load_state("networkidle")
            await self._random_delay(3, 5)
            
            # Check if login was successful
            login_form = await self.page.query_selector('input[name="email"]')
            if login_form:
                logger.error("Login failed - still on login page")
                return False
            
            # Check for 2FA or security checkpoint
            checkpoint = await self.page.query_selector('[id*="checkpoint"]')
            if checkpoint:
                logger.error("Login requires 2FA or security verification - please log in manually first")
                return False
            
            self._logged_in = True
            logger.info("Successfully logged in")
            
            # Save session
            await self._save_session()
            
            return True
            
        except Exception as e:
            logger.error("Login failed", error=str(e))
            return False
    
    async def _save_session(self):
        """Save the browser session for future use."""
        try:
            session_path = config.session_path
            session_path.mkdir(parents=True, exist_ok=True)
            
            await self.context.storage_state(path=str(session_path / "facebook_session.json"))
            logger.info("Session saved")
            
        except Exception as e:
            logger.warning("Failed to save session", error=str(e))
    
    async def scrape_group(self, group_url: str, group_name: str) -> list[RawPost]:
        """Scrape posts from a Facebook group."""
        logger.info("Scraping group", group_name=group_name)
        
        if not self._logged_in:
            if not await self.login():
                logger.error("Cannot scrape - not logged in")
                return []
        
        posts = []
        
        try:
            # Navigate to group
            await self.page.goto(group_url, wait_until="networkidle")
            await self._random_delay()
            
            # Scroll to load more posts
            for _ in range(3):  # Scroll a few times
                await self.page.evaluate("window.scrollBy(0, 1000)")
                await self._random_delay(1, 2)
            
            # Extract posts
            post_elements = await self.page.query_selector_all('[data-pagelet*="FeedUnit"], [role="article"]')
            logger.info(f"Found {len(post_elements)} post elements")
            
            for element in post_elements[:config.posts_per_group]:
                try:
                    post = await self._extract_post(element, group_name, group_url)
                    if post:
                        posts.append(post)
                except Exception as e:
                    logger.warning("Failed to extract post", error=str(e))
                    continue
            
            logger.info(f"Extracted {len(posts)} posts from {group_name}")
            
        except Exception as e:
            logger.error("Error scraping group", group_name=group_name, error=str(e))
        
        return posts
    
    async def _extract_post(self, element, group_name: str, group_url: str) -> Optional[RawPost]:
        """Extract data from a single post element."""
        try:
            # Get post content
            content_el = await element.query_selector('[data-ad-preview="message"], [data-ad-comet-preview="message"]')
            if not content_el:
                # Try alternative selectors
                content_el = await element.query_selector('div[dir="auto"]')
            
            if not content_el:
                return None
            
            content = await content_el.inner_text()
            if not content or len(content) < 20:  # Skip very short posts
                return None
            
            # Get post URL/ID
            post_url = ""
            post_id = ""
            link_els = await element.query_selector_all('a[href*="/posts/"], a[href*="/permalink/"]')
            for link_el in link_els:
                href = await link_el.get_attribute("href")
                if href:
                    post_url = href if href.startswith("http") else f"https://www.facebook.com{href}"
                    # Extract post ID from URL
                    match = re.search(r'/posts/(\d+)|/permalink/(\d+)', href)
                    if match:
                        post_id = match.group(1) or match.group(2)
                    break
            
            if not post_id:
                # Generate a pseudo-ID from content hash
                import hashlib
                post_id = hashlib.md5(content.encode()).hexdigest()[:16]
            
            # Get author name
            author_name = None
            author_el = await element.query_selector('a[role="link"] strong, h4 a')
            if author_el:
                author_name = await author_el.inner_text()
            
            # Get images
            images = []
            img_els = await element.query_selector_all('img[src*="scontent"]')
            for img_el in img_els:
                src = await img_el.get_attribute("src")
                if src and "emoji" not in src.lower():
                    images.append(src)
            
            # Get posted time (this is tricky with Facebook)
            posted_at = None
            time_el = await element.query_selector('abbr, span[id*="jsc_c"]')
            if time_el:
                # Facebook often uses relative times, we'd need to parse them
                pass
            
            return RawPost(
                post_id=post_id,
                content=content,
                author_name=author_name,
                post_url=post_url,
                images=images[:5],  # Limit to 5 images
                posted_at=posted_at,
                group_name=group_name,
                group_url=group_url
            )
            
        except Exception as e:
            logger.warning("Error extracting post data", error=str(e))
            return None
    
    async def scrape_all_groups(self) -> list[RawPost]:
        """Scrape all configured Facebook groups."""
        all_posts = []
        
        for group in config.facebook_groups:
            posts = await self.scrape_group(group["url"], group["name"])
            all_posts.extend(posts)
            await self._random_delay()  # Delay between groups
        
        return all_posts
    
    async def stop(self):
        """Close the browser."""
        if self.context:
            await self._save_session()
        if self.browser:
            await self.browser.close()
        logger.info("Facebook scraper stopped")


async def run_scraper() -> list[RawPost]:
    """Convenience function to run the scraper."""
    scraper = FacebookScraper()
    try:
        await scraper.start()
        posts = await scraper.scrape_all_groups()
        return posts
    finally:
        await scraper.stop()
