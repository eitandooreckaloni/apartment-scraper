"""Facebook group scraper using facebook_scraper library.

This is a lighter-weight alternative to the Playwright-based scraper.
Uses HTTP requests instead of browser automation.
"""

import re
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator
from dataclasses import dataclass

import structlog
from facebook_scraper import get_posts, set_cookies

from ..config import config
from ..logging_config import print_status, print_error, print_warning, print_success

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
    """Scrapes apartment listings from Facebook groups using facebook_scraper library."""
    
    def __init__(self):
        self._cookies_loaded = False
        self._cookies_path = config.session_path / "facebook_cookies.json"
    
    def _random_delay(self, min_sec: Optional[float] = None, max_sec: Optional[float] = None):
        """Wait a random amount of time to appear more human."""
        min_sec = min_sec or config.scraper_min_delay
        max_sec = max_sec or config.scraper_max_delay
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def _extract_group_id(self, url: str) -> Optional[int]:
        """Extract numeric group ID from Facebook group URL."""
        # Match URLs like https://www.facebook.com/groups/305724686290054
        match = re.search(r'/groups/(\d+)', url)
        if match:
            return int(match.group(1))
        
        # Some groups use slugs - we'll need to handle those differently
        # For now, return None and skip these groups
        logger.warning("Could not extract numeric group ID from URL", url=url)
        return None
    
    async def start(self):
        """Initialize the scraper by loading cookies."""
        print_status("Starting Facebook scraper (library mode)...")
        logger.info("Starting Facebook scraper using facebook_scraper library")
        
        # Try to load cookies
        if self._cookies_path.exists():
            try:
                set_cookies(str(self._cookies_path))
                self._cookies_loaded = True
                print_success("Loaded Facebook cookies")
                logger.info("Cookies loaded from file", path=str(self._cookies_path))
            except Exception as e:
                print_warning(f"Could not load cookies: {str(e)[:50]}")
                logger.warning("Failed to load cookies", error=str(e))
        else:
            print_warning("No cookies file found - scraping may be limited")
            print_warning(f"  Expected at: {self._cookies_path}")
            logger.warning("Cookies file not found", expected_path=str(self._cookies_path))
    
    async def stop(self):
        """Clean up (nothing to do for library-based scraper)."""
        print_status("Facebook scraper stopped")
        logger.info("Facebook scraper stopped")
    
    def _to_raw_post(self, post: dict, group_name: str, group_url: str) -> Optional[RawPost]:
        """Convert facebook_scraper post dict to RawPost."""
        try:
            # Get post content
            content = post.get('text') or post.get('post_text') or ''
            if not content or len(content.strip()) < 20:
                return None
            
            # Get post ID
            post_id = str(post.get('post_id', ''))
            if not post_id:
                # Generate from content hash
                import hashlib
                post_id = hashlib.md5(content.encode()).hexdigest()[:16]
            
            # Get post URL
            post_url = post.get('post_url', '')
            if not post_url and post_id:
                post_url = f"https://www.facebook.com/{post_id}"
            
            # Get author name
            author_name = post.get('username') or post.get('user_id')
            
            # Get images
            images = []
            if post.get('images'):
                images = list(post['images'])[:5]  # Limit to 5 images
            elif post.get('image'):
                images = [post['image']]
            
            # Get posted time
            posted_at = None
            if post.get('time'):
                posted_at = post['time']
            
            return RawPost(
                post_id=post_id,
                content=content.strip(),
                author_name=author_name,
                post_url=post_url,
                images=images,
                posted_at=posted_at,
                group_name=group_name,
                group_url=group_url
            )
            
        except Exception as e:
            logger.warning("Error converting post to RawPost", error=str(e))
            return None
    
    async def scrape_group(self, group_url: str, group_name: str) -> list[RawPost]:
        """Scrape posts from a Facebook group."""
        print_status(f"Scraping: {group_name}")
        logger.info("Scraping group", group_name=group_name, group_url=group_url)
        
        posts = []
        
        # Extract group ID from URL
        group_id = self._extract_group_id(group_url)
        if not group_id:
            print_error(f"  Could not extract group ID from URL")
            logger.error("Could not extract group ID", group_url=group_url)
            return []
        
        try:
            # Calculate pages based on posts_per_group config
            # facebook_scraper returns ~10-20 posts per page
            pages = max(1, config.posts_per_group // 10)
            
            # Get posts from the group
            post_generator = get_posts(
                group=group_id,
                pages=pages,
                cookies=str(self._cookies_path) if self._cookies_loaded else None,
                options={
                    "allow_extra_requests": False,  # Be conservative to avoid blocks
                    "posts_per_page": min(20, config.posts_per_group),
                }
            )
            
            # Process posts
            count = 0
            for post in post_generator:
                if count >= config.posts_per_group:
                    break
                
                raw_post = self._to_raw_post(post, group_name, group_url)
                if raw_post:
                    posts.append(raw_post)
                    count += 1
                
                # Small delay between processing posts
                self._random_delay(0.1, 0.3)
            
            print_status(f"  Found {len(posts)} posts")
            logger.info(f"Extracted {len(posts)} posts", group_name=group_name)
            
        except Exception as e:
            error_str = str(e)
            if "login" in error_str.lower() or "cookie" in error_str.lower():
                print_error(f"  Authentication required - please update cookies")
                logger.error("Authentication error", group_name=group_name, error=error_str)
            elif "blocked" in error_str.lower() or "rate" in error_str.lower():
                print_error(f"  Rate limited or blocked - try again later")
                logger.error("Rate limited", group_name=group_name, error=error_str)
            else:
                print_error(f"  Failed: {error_str[:50]}")
                logger.error("Error scraping group", group_name=group_name, error=error_str)
        
        return posts
    
    async def scrape_all_groups(self, ensure_membership: bool = True) -> list[RawPost]:
        """
        Scrape all configured Facebook groups.
        
        Args:
            ensure_membership: Ignored for library-based scraper (can't check membership via HTTP).
        """
        all_posts = []
        total_groups = len(config.facebook_groups)
        
        print_status(f"Scraping {total_groups} groups...")
        logger.info("Starting to scrape all groups", total_groups=total_groups)
        
        for i, group in enumerate(config.facebook_groups, 1):
            group_url = group["url"]
            group_name = group["name"]
            
            print_status(f"  [{i}/{total_groups}] {group_name}")
            
            posts = await self.scrape_group(group_url, group_name)
            all_posts.extend(posts)
            
            # Delay between groups to avoid rate limiting
            if i < total_groups:
                self._random_delay()
        
        print_status(f"Total posts collected: {len(all_posts)}")
        logger.info("Scraping complete", total_posts=len(all_posts))
        
        return all_posts


async def run_scraper() -> list[RawPost]:
    """Convenience function to run the scraper."""
    scraper = FacebookScraper()
    try:
        await scraper.start()
        posts = await scraper.scrape_all_groups()
        return posts
    finally:
        await scraper.stop()
