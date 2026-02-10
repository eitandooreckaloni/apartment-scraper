"""Facebook group scraper using Apify's Facebook Posts Scraper actor.

This scraper uses Apify's cloud-based Facebook scraper which is more reliable
than direct scraping methods, though it incurs per-run costs (~$0.05/run).
"""

import os
import time
import hashlib
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import structlog
from apify_client import ApifyClient

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


class ApifyFacebookScraper:
    """Scrapes apartment listings from Facebook groups using Apify's Facebook Posts Scraper."""
    
    def __init__(self):
        api_token = config.apify_api_token
        if not api_token:
            raise ValueError(
                "APIFY_API_TOKEN not set. Get your token at https://console.apify.com/account/integrations"
            )
        self.client = ApifyClient(api_token)
        self.actor_id = config.facebook_apify_actor_id
        self.timeout_seconds = config.facebook_apify_timeout
        self.max_posts = config.facebook_apify_max_posts
    
    async def start(self):
        """Initialize the scraper."""
        print_status("Starting Facebook scraper (Apify mode)...")
        logger.info("Starting Facebook scraper using Apify", actor_id=self.actor_id)
    
    async def stop(self):
        """Clean up (nothing to do for Apify-based scraper)."""
        print_status("Facebook scraper stopped")
        logger.info("Facebook scraper stopped")
    
    def _transform_to_raw_post(
        self, item: dict, group_name: str, group_url: str
    ) -> Optional[RawPost]:
        """Transform Apify output item to RawPost format."""
        try:
            # Get post content - try various field names
            content = (
                item.get('text') or 
                item.get('message') or 
                item.get('content') or 
                item.get('postText') or
                ''
            )
            
            # Skip posts with no/minimal content
            if not content or len(content.strip()) < 20:
                return None
            
            # Get post ID
            post_id = str(
                item.get('postId') or 
                item.get('id') or 
                item.get('post_id') or
                ''
            )
            if not post_id:
                # Generate from content hash
                post_id = hashlib.md5(content.encode()).hexdigest()[:16]
            
            # Get post URL
            post_url = (
                item.get('url') or 
                item.get('postUrl') or 
                item.get('post_url') or
                ''
            )
            if not post_url and post_id:
                post_url = f"https://www.facebook.com/{post_id}"
            
            # Get author name from nested author object or direct fields
            author_name = None
            author = item.get('author', {})
            if isinstance(author, dict):
                author_name = author.get('name') or author.get('username')
            if not author_name:
                author_name = (
                    item.get('authorName') or 
                    item.get('username') or 
                    item.get('user_id')
                )
            
            # Extract images from attachments
            images = []
            attachments = item.get('attachments', [])
            if isinstance(attachments, list):
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        # Only include photo attachments
                        if attachment.get('type') == 'photo':
                            img_url = attachment.get('url')
                            if img_url:
                                images.append(img_url)
                                if len(images) >= 5:  # Limit to 5 images
                                    break
            
            # Fallback to direct image fields
            if not images:
                if item.get('images'):
                    images = list(item['images'])[:5]
                elif item.get('image'):
                    images = [item['image']]
            
            # Parse timestamp
            posted_at = None
            timestamp = item.get('timestamp') or item.get('time') or item.get('createdTime')
            if timestamp:
                try:
                    if isinstance(timestamp, (int, float)):
                        # Unix timestamp - could be seconds or milliseconds
                        if timestamp > 1e12:  # Milliseconds
                            timestamp = timestamp / 1000
                        posted_at = datetime.fromtimestamp(timestamp)
                    elif isinstance(timestamp, str):
                        # Try ISO format
                        posted_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except Exception as e:
                    logger.debug("Could not parse timestamp", timestamp=timestamp, error=str(e))
            
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
            logger.warning("Error transforming Apify item to RawPost", error=str(e))
            return None
    
    def _run_actor_sync(self, group_urls: list[str]) -> list[dict]:
        """Run the Apify actor synchronously and return results."""
        # Prepare actor input - the Facebook Posts Scraper expects 'pageUrls'
        actor_input = {
            "pageUrls": group_urls,
            "maxPosts": self.max_posts,
        }
        
        logger.info("Starting Apify actor run", actor_id=self.actor_id, urls=group_urls)
        
        try:
            # Run the actor and wait for it to finish
            run = self.client.actor(self.actor_id).call(
                run_input=actor_input,
                timeout_secs=self.timeout_seconds
            )
            
            # Check run status
            status = run.get('status')
            if status != 'SUCCEEDED':
                logger.error("Apify actor run did not succeed", status=status, run_id=run.get('id'))
                return []
            
            # Fetch results from the default dataset
            dataset_id = run.get('defaultDatasetId')
            if not dataset_id:
                logger.error("No dataset ID in actor run result")
                return []
            
            # Get all items from the dataset
            items = list(self.client.dataset(dataset_id).iterate_items())
            logger.info(f"Fetched {len(items)} items from Apify dataset", dataset_id=dataset_id)
            
            return items
            
        except Exception as e:
            logger.error("Error running Apify actor", error=str(e))
            return []
    
    async def scrape_group(self, group_url: str, group_name: str) -> list[RawPost]:
        """Scrape posts from a single Facebook group."""
        print_status(f"Scraping: {group_name}")
        logger.info("Scraping group via Apify", group_name=group_name, group_url=group_url)
        
        posts = []
        
        try:
            # Run actor for this single group
            items = self._run_actor_sync([group_url])
            
            # Transform results to RawPost
            for item in items:
                raw_post = self._transform_to_raw_post(item, group_name, group_url)
                if raw_post:
                    posts.append(raw_post)
            
            print_status(f"  Found {len(posts)} posts")
            logger.info(f"Extracted {len(posts)} posts", group_name=group_name)
            
        except Exception as e:
            error_str = str(e)
            print_error(f"  Failed: {error_str[:50]}")
            logger.error("Error scraping group via Apify", group_name=group_name, error=error_str)
        
        return posts
    
    async def scrape_all_groups(self, ensure_membership: bool = True) -> list[RawPost]:
        """
        Scrape all configured Facebook groups.
        
        The Apify actor can handle multiple URLs in a single run, which is more
        efficient than running separate calls for each group.
        
        Args:
            ensure_membership: Ignored for Apify-based scraper (handled by Apify).
        """
        all_posts = []
        groups = config.facebook_groups
        total_groups = len(groups)
        
        if not groups:
            print_warning("No Facebook groups configured")
            logger.warning("No Facebook groups configured")
            return []
        
        print_status(f"Scraping {total_groups} groups via Apify...")
        logger.info("Starting to scrape all groups via Apify", total_groups=total_groups)
        
        # Collect all group URLs for batch processing
        group_urls = [g["url"] for g in groups]
        group_name_map = {g["url"]: g["name"] for g in groups}
        
        try:
            # Run actor for all groups at once (more efficient)
            items = self._run_actor_sync(group_urls)
            
            print_success(f"Apify returned {len(items)} total items")
            logger.info(f"Apify returned {len(items)} items for all groups")
            
            # Transform results to RawPost
            # Note: We may need to determine which group each post came from
            for item in items:
                # Try to determine the source group from the item
                item_url = item.get('url') or item.get('postUrl') or ''
                
                # Find matching group by checking if post URL contains group ID
                matched_group_name = "Facebook Group"
                matched_group_url = ""
                
                for group in groups:
                    group_url = group["url"]
                    # Extract group ID from URL
                    if '/groups/' in group_url:
                        group_id = group_url.split('/groups/')[-1].rstrip('/')
                        if group_id and group_id in item_url:
                            matched_group_name = group["name"]
                            matched_group_url = group_url
                            break
                
                # If we couldn't match, use the first group as default
                if not matched_group_url and groups:
                    matched_group_name = groups[0]["name"]
                    matched_group_url = groups[0]["url"]
                
                raw_post = self._transform_to_raw_post(item, matched_group_name, matched_group_url)
                if raw_post:
                    all_posts.append(raw_post)
            
            print_status(f"Total posts processed: {len(all_posts)}")
            logger.info("Scraping complete", total_posts=len(all_posts))
            
        except Exception as e:
            error_str = str(e)
            print_error(f"Apify scraping failed: {error_str[:80]}")
            logger.error("Error scraping groups via Apify", error=error_str)
        
        return all_posts


async def run_scraper() -> list[RawPost]:
    """Convenience function to run the scraper."""
    scraper = ApifyFacebookScraper()
    try:
        await scraper.start()
        posts = await scraper.scrape_all_groups()
        return posts
    finally:
        await scraper.stop()
