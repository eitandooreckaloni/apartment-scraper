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
    """Scrapes apartment listings from Facebook groups."""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._logged_in = False
        self._group_statuses: dict[str, str] = {}  # Track group membership statuses
    
    async def _random_delay(self, min_sec: Optional[int] = None, max_sec: Optional[int] = None):
        """Wait a random amount of time to appear more human."""
        min_sec = min_sec or config.scraper_min_delay
        max_sec = max_sec or config.scraper_max_delay
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def start(self):
        """Start the browser and load session if available."""
        print_status("Opening browser...")
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
            print_status("Loading saved Facebook session...")
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
            print_status("Checking Facebook login...")
            await self.page.goto("https://www.facebook.com", wait_until="networkidle")
            await self._random_delay(2, 4)
            
            # Check for login form or user menu
            login_form = await self.page.query_selector('input[name="email"]')
            if login_form:
                self._logged_in = False
                print_warning("Not logged into Facebook - please authenticate first")
                logger.info("Not logged in - need to authenticate")
                return False
            
            self._logged_in = True
            print_success("Logged into Facebook")
            logger.info("Already logged in")
            return True
            
        except Exception as e:
            print_error(f"Could not check login status: {str(e)}")
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
    
    async def check_group_membership(self, group_url: str, group_name: str) -> str:
        """
        Check membership status for a Facebook group.
        
        Returns:
            "member" - Already a member of the group
            "pending" - Membership request is pending approval
            "not_member" - Not a member, can attempt to join
            "error" - Could not determine status
        """
        logger.info("Checking group membership", group_name=group_name, group_url=group_url)
        
        if not self._logged_in:
            if not await self.login():
                logger.error("Cannot check membership - not logged in")
                return "error"
        
        try:
            # Navigate to group
            await self.page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)  # Wait for dynamic content
            
            current_url = self.page.url
            page_content = await self.page.content()
            
            # Check if redirected to login
            login_form = await self.page.query_selector('input[name="email"]')
            if login_form:
                logger.warning("Redirected to login while checking group membership")
                self._logged_in = False
                return "error"
            
            # Check for "Content isn't available" or group not found
            not_available_selectors = [
                'text="Content isn\'t available"',
                'text="This content isn\'t available"',
                'text="This group is private"',
            ]
            for selector in not_available_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        logger.warning("Group content not available", group_name=group_name)
                        return "error"
                except:
                    pass
            
            # Check for pending membership request indicators
            # These typically appear as "Pending" button or "Cancel Request" text
            pending_selectors = [
                '[aria-label*="Pending"]',
                '[aria-label*="Cancel request"]',
                'div[role="button"]:has-text("Pending")',
                'div[role="button"]:has-text("Cancel Request")',
                'span:has-text("Your request is pending")',
            ]
            for selector in pending_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        logger.info("Group membership is pending", group_name=group_name)
                        return "pending"
                except:
                    pass
            
            # Also check page text for pending indicators
            if "pending" in page_content.lower() and "request" in page_content.lower():
                # More specific check - look for the pending button area
                pending_text = await self.page.query_selector('text=/pending/i')
                if pending_text:
                    logger.info("Group membership is pending (text match)", group_name=group_name)
                    return "pending"
            
            # Check for "Join Group" button - indicates not a member
            join_selectors = [
                '[aria-label*="Join group"]',
                '[aria-label*="Join Group"]',
                'div[role="button"]:has-text("Join group")',
                'div[role="button"]:has-text("Join Group")',
                'span:has-text("Join group")',
                'span:has-text("Join Group")',
            ]
            for selector in join_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        # Verify it's visible
                        is_visible = await element.is_visible()
                        if is_visible:
                            logger.info("Not a member of group - join button found", group_name=group_name)
                            return "not_member"
                except:
                    pass
            
            # If no join button and no pending status, assume we're a member
            # Additional check: look for feed content or member-only elements
            member_indicators = [
                '[data-pagelet*="FeedUnit"]',
                '[role="article"]',
                '[aria-label*="Create a post"]',
                '[aria-label*="Write something"]',
            ]
            for selector in member_indicators:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        logger.info("Already a member of group", group_name=group_name)
                        return "member"
                except:
                    pass
            
            # If we got here without finding definitive indicators, assume member
            # (no join button present usually means we're in)
            logger.info("Assuming member status (no join button found)", group_name=group_name)
            return "member"
            
        except Exception as e:
            logger.error("Error checking group membership", group_name=group_name, error=str(e))
            return "error"
    
    async def join_group(self, group_url: str, group_name: str) -> str:
        """
        Attempt to join a Facebook group.
        
        Returns:
            "joined" - Successfully joined the group (instant join)
            "pending" - Join request submitted, awaiting approval
            "already_member" - Already a member of the group
            "failed" - Could not join the group
        """
        logger.info("Attempting to join group", group_name=group_name, group_url=group_url)
        
        if not self._logged_in:
            if not await self.login():
                logger.error("Cannot join group - not logged in")
                return "failed"
        
        try:
            # First check current membership status
            status = await self.check_group_membership(group_url, group_name)
            
            if status == "member":
                logger.info("Already a member of group", group_name=group_name)
                return "already_member"
            
            if status == "pending":
                logger.info("Join request already pending", group_name=group_name)
                return "pending"
            
            if status == "error":
                logger.error("Cannot determine membership status", group_name=group_name)
                return "failed"
            
            # Status is "not_member" - try to join
            # Navigate to group if not already there
            if group_url not in self.page.url:
                await self.page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
            
            # Find and click the Join button
            join_selectors = [
                '[aria-label*="Join group"]',
                '[aria-label*="Join Group"]',
                'div[role="button"]:has-text("Join group")',
                'div[role="button"]:has-text("Join Group")',
            ]
            
            join_button = None
            for selector in join_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        join_button = element
                        break
                except:
                    continue
            
            if not join_button:
                logger.error("Could not find Join button", group_name=group_name)
                return "failed"
            
            # Click the join button
            await self._random_delay(1, 2)
            await join_button.click()
            logger.info("Clicked Join button", group_name=group_name)
            
            # Wait for the action to complete
            await asyncio.sleep(3)
            await self._random_delay(2, 4)
            
            # Check if there's a membership questions dialog
            # Some groups require answering questions before joining
            questions_dialog = await self.page.query_selector('[aria-label*="Answer questions"]')
            if questions_dialog:
                logger.warning("Group requires answering questions - skipping for now", group_name=group_name)
                # Close the dialog if possible
                close_button = await self.page.query_selector('[aria-label="Close"]')
                if close_button:
                    await close_button.click()
                return "failed"
            
            # Check the result - did we join instantly or is it pending?
            # Re-check membership status
            await asyncio.sleep(2)
            
            # Look for pending indicators
            pending_selectors = [
                '[aria-label*="Pending"]',
                '[aria-label*="Cancel request"]',
                'div[role="button"]:has-text("Pending")',
                'div[role="button"]:has-text("Cancel Request")',
            ]
            for selector in pending_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info("Join request is pending approval", group_name=group_name)
                        return "pending"
                except:
                    pass
            
            # Check if join button is still there (join failed)
            for selector in join_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.warning("Join button still visible - join may have failed", group_name=group_name)
                        return "failed"
                except:
                    pass
            
            # Check for member indicators (successful instant join)
            member_indicators = [
                '[aria-label*="Create a post"]',
                '[aria-label*="Write something"]',
                'div[role="button"]:has-text("Joined")',
                '[data-pagelet*="FeedUnit"]',
            ]
            for selector in member_indicators:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        logger.info("Successfully joined group", group_name=group_name)
                        await self._save_session()  # Save session after successful join
                        return "joined"
                except:
                    pass
            
            # If we can't determine, assume pending (safer assumption)
            logger.info("Join result unclear - assuming pending", group_name=group_name)
            return "pending"
            
        except Exception as e:
            logger.error("Error joining group", group_name=group_name, error=str(e))
            return "failed"
    
    async def ensure_group_memberships(self) -> dict[str, str]:
        """
        Check and ensure membership in all configured Facebook groups.
        
        Iterates through all groups in config and:
        - Checks membership status for each
        - Attempts to join groups where not a member (if auto_join is enabled)
        - Returns a dict mapping group URLs to their status
        
        Returns:
            Dict mapping group URL to status:
            - "member" - Already a member or successfully joined
            - "pending" - Membership request is pending
            - "failed" - Could not join
            - "skipped" - Auto-join disabled, not a member
        """
        print_status("Checking group memberships...")
        logger.info("Ensuring group memberships for all configured groups")
        
        if not self._logged_in:
            if not await self.login():
                print_error("Cannot check memberships - not logged in")
                logger.error("Cannot ensure memberships - not logged in")
                return {}
        
        auto_join = getattr(config, 'auto_join_groups', True)
        group_statuses = {}
        total_groups = len(config.facebook_groups)
        
        for i, group in enumerate(config.facebook_groups, 1):
            group_url = group["url"]
            group_name = group["name"]
            
            print_status(f"  [{i}/{total_groups}] {group_name}")
            logger.info("Processing group", group_name=group_name)
            
            # Check current membership status
            status = await self.check_group_membership(group_url, group_name)
            
            if status == "member":
                group_statuses[group_url] = "member"
                logger.info("Already a member", group_name=group_name)
            
            elif status == "pending":
                group_statuses[group_url] = "pending"
                print_warning(f"      Waiting for admin approval")
                logger.info("Membership pending approval", group_name=group_name)
            
            elif status == "not_member":
                if auto_join:
                    # Attempt to join
                    join_result = await self.join_group(group_url, group_name)
                    
                    if join_result == "joined":
                        group_statuses[group_url] = "member"
                        print_success(f"      Joined!")
                    elif join_result == "pending":
                        group_statuses[group_url] = "pending"
                        print_warning(f"      Join request sent")
                    elif join_result == "already_member":
                        group_statuses[group_url] = "member"
                    else:
                        group_statuses[group_url] = "failed"
                        print_warning(f"      Could not join")
                else:
                    group_statuses[group_url] = "skipped"
                    logger.info("Auto-join disabled, skipping", group_name=group_name)
            
            else:  # status == "error"
                group_statuses[group_url] = "failed"
                logger.warning("Could not determine membership status", group_name=group_name)
            
            # Delay between groups to avoid rate limiting
            await self._random_delay()
        
        # Human-friendly summary
        members = sum(1 for s in group_statuses.values() if s == "member")
        pending = sum(1 for s in group_statuses.values() if s == "pending")
        failed = sum(1 for s in group_statuses.values() if s in ("failed", "skipped"))
        
        print("")
        print_status(f"Group access: {members}/{total_groups} groups ready")
        if pending > 0:
            print_warning(f"  {pending} groups pending admin approval")
        if failed > 0:
            print_warning(f"  {failed} groups not accessible")
        print("")
        
        logger.info(
            "Group membership summary",
            total_groups=len(group_statuses),
            members=members,
            pending=pending,
            failed_or_skipped=failed
        )
        
        return group_statuses
    
    async def scrape_group(self, group_url: str, group_name: str) -> list[RawPost]:
        """Scrape posts from a Facebook group."""
        print_status(f"Scraping: {group_name}")
        logger.info("Scraping group", group_name=group_name)
        
        if not self._logged_in:
            if not await self.login():
                print_error("Cannot scrape - not logged in")
                logger.error("Cannot scrape - not logged in")
                return []
        
        posts = []
        
        try:
            # Navigate to group - use domcontentloaded instead of networkidle to avoid timeout
            try:
                await self.page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for dynamic content to load
                await asyncio.sleep(3)
                
            except Exception as nav_error:
                raise
            
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
            
            print_status(f"  Found {len(posts)} posts")
            logger.info(f"Extracted {len(posts)} posts from {group_name}")
            
        except Exception as e:
            if "Timeout" in str(e):
                print_warning(f"  Timeout - Facebook may be slow")
            else:
                print_error(f"  Failed: {str(e)[:50]}")
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
    
    async def scrape_all_groups(self, ensure_membership: bool = True) -> list[RawPost]:
        """
        Scrape all configured Facebook groups.
        
        Args:
            ensure_membership: If True, check and attempt to join groups before scraping.
                             This helps with new accounts that aren't yet members.
        """
        all_posts = []
        
        # First, ensure we're members of all groups (if enabled)
        if ensure_membership:
            self._group_statuses = await self.ensure_group_memberships()
        
        # Now scrape only the groups we're members of
        groups_scraped = 0
        groups_skipped = 0
        total_groups = len(config.facebook_groups)
        
        print_status(f"Scraping {total_groups} groups...")
        
        for i, group in enumerate(config.facebook_groups, 1):
            group_url = group["url"]
            group_name = group["name"]
            
            # Check if we should scrape this group
            status = self._group_statuses.get(group_url, "unknown")
            
            if status == "member":
                posts = await self.scrape_group(group_url, group_name)
                all_posts.extend(posts)
                groups_scraped += 1
                await self._random_delay()  # Delay between groups
            
            elif status == "pending":
                print_warning(f"Skipping: {group_name} (pending approval)")
                logger.warning(
                    "Skipping group - membership pending approval",
                    group_name=group_name
                )
                groups_skipped += 1
            
            elif status in ("failed", "skipped"):
                print_warning(f"Skipping: {group_name} (not a member)")
                logger.warning(
                    "Skipping group - not a member",
                    group_name=group_name,
                    status=status
                )
                groups_skipped += 1
            
            else:
                # Unknown status - try to scrape anyway (might work if already member)
                logger.info(
                    "Unknown membership status - attempting to scrape anyway",
                    group_name=group_name
                )
                posts = await self.scrape_group(group_url, group_name)
                all_posts.extend(posts)
                groups_scraped += 1
                await self._random_delay()
        
        logger.info(
            "Scraping complete",
            total_posts=len(all_posts),
            groups_scraped=groups_scraped,
            groups_skipped=groups_skipped
        )
        
        return all_posts
    
    async def stop(self):
        """Close the browser."""
        if self.context:
            await self._save_session()
        if self.browser:
            await self.browser.close()
        print_status("Browser closed")
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
