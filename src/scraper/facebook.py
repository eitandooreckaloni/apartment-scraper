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

# #region agent log
import time as _dbg_time
_DBG_LOG_PATH = "/Users/eitan/Documents/git-repos/apartment-scraper/.cursor/debug.log"
def _dbg_log(loc, msg, data=None, hyp=None):
    import json as _j
    payload = {"location": loc, "message": msg, "data": data or {}, "hypothesisId": hyp, "timestamp": int(_dbg_time.time()*1000)}
    with open(_DBG_LOG_PATH, "a") as f: f.write(_j.dumps(payload) + "\n")
# #endregion


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
            # #region agent log
            _dbg_log("facebook.py:_check_login_status:start", "Starting login status check", {"url": "https://www.facebook.com"}, "B")
            # #endregion
            await self.page.goto("https://www.facebook.com", wait_until="networkidle")
            await self._random_delay(2, 4)
            
            # #region agent log
            current_url = self.page.url
            page_title = await self.page.title()
            _dbg_log("facebook.py:_check_login_status:after_nav", "After navigation to facebook.com", {"current_url": current_url, "page_title": page_title}, "B")
            # #endregion
            
            # Check for login form or user menu
            login_form = await self.page.query_selector('input[name="email"]')
            if login_form:
                self._logged_in = False
                logger.info("Not logged in - need to authenticate")
                # #region agent log
                _dbg_log("facebook.py:_check_login_status:not_logged_in", "Login form detected - not logged in", {}, "B")
                # #endregion
                return False
            
            self._logged_in = True
            logger.info("Already logged in")
            # #region agent log
            _dbg_log("facebook.py:_check_login_status:logged_in", "No login form - appears logged in", {}, "B")
            # #endregion
            return True
            
        except Exception as e:
            logger.error("Error checking login status", error=str(e))
            # #region agent log
            _dbg_log("facebook.py:_check_login_status:error", "Error during login check", {"error": str(e)}, "B")
            # #endregion
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
        logger.info("Ensuring group memberships for all configured groups")
        
        if not self._logged_in:
            if not await self.login():
                logger.error("Cannot ensure memberships - not logged in")
                return {}
        
        auto_join = getattr(config, 'auto_join_groups', True)
        group_statuses = {}
        
        for group in config.facebook_groups:
            group_url = group["url"]
            group_name = group["name"]
            
            logger.info("Processing group", group_name=group_name)
            
            # Check current membership status
            status = await self.check_group_membership(group_url, group_name)
            
            if status == "member":
                group_statuses[group_url] = "member"
                logger.info("Already a member", group_name=group_name)
            
            elif status == "pending":
                group_statuses[group_url] = "pending"
                logger.info("Membership pending approval", group_name=group_name)
            
            elif status == "not_member":
                if auto_join:
                    # Attempt to join
                    join_result = await self.join_group(group_url, group_name)
                    
                    if join_result == "joined":
                        group_statuses[group_url] = "member"
                    elif join_result == "pending":
                        group_statuses[group_url] = "pending"
                    elif join_result == "already_member":
                        group_statuses[group_url] = "member"
                    else:
                        group_statuses[group_url] = "failed"
                else:
                    group_statuses[group_url] = "skipped"
                    logger.info("Auto-join disabled, skipping", group_name=group_name)
            
            else:  # status == "error"
                group_statuses[group_url] = "failed"
                logger.warning("Could not determine membership status", group_name=group_name)
            
            # Delay between groups to avoid rate limiting
            await self._random_delay()
        
        # Log summary
        members = sum(1 for s in group_statuses.values() if s == "member")
        pending = sum(1 for s in group_statuses.values() if s == "pending")
        failed = sum(1 for s in group_statuses.values() if s in ("failed", "skipped"))
        
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
        logger.info("Scraping group", group_name=group_name)
        
        if not self._logged_in:
            if not await self.login():
                logger.error("Cannot scrape - not logged in")
                return []
        
        posts = []
        
        try:
            # #region agent log
            _dbg_log("facebook.py:scrape_group:before_nav", "About to navigate to group", {"group_url": group_url, "group_name": group_name, "logged_in": self._logged_in}, "A,E")
            nav_start = _dbg_time.time()
            # #endregion
            
            # Navigate to group - use domcontentloaded instead of networkidle to avoid timeout
            # Then wait for network to settle separately with a shorter timeout
            try:
                await self.page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
                # #region agent log
                after_dom = _dbg_time.time()
                _dbg_log("facebook.py:scrape_group:dom_loaded", "DOM content loaded", {"elapsed_ms": int((after_dom - nav_start)*1000), "current_url": self.page.url}, "A")
                # #endregion
                
                # Now wait a bit for dynamic content, but don't wait for full networkidle
                await asyncio.sleep(3)
                
                # #region agent log
                current_url = self.page.url
                page_title = await self.page.title()
                _dbg_log("facebook.py:scrape_group:after_sleep", "After 3s wait", {"current_url": current_url, "page_title": page_title, "total_elapsed_ms": int((_dbg_time.time() - nav_start)*1000)}, "A,B,C")
                # #endregion
                
                # Check for blocking dialogs/modals (cookie consent, login redirect, captcha)
                # #region agent log
                dialog_selectors = [
                    '[data-testid="cookie-policy-manage-dialog"]',
                    '[role="dialog"]',
                    'input[name="email"]',  # Login form
                    '[id*="captcha"]',
                    '[id*="checkpoint"]'
                ]
                found_dialogs = []
                for sel in dialog_selectors:
                    elem = await self.page.query_selector(sel)
                    if elem:
                        found_dialogs.append(sel)
                _dbg_log("facebook.py:scrape_group:dialog_check", "Checked for blocking elements", {"found_dialogs": found_dialogs, "current_url": current_url}, "C,D")
                # #endregion
                
            except Exception as nav_error:
                # #region agent log
                _dbg_log("facebook.py:scrape_group:nav_error", "Navigation error", {"error": str(nav_error), "type": type(nav_error).__name__, "elapsed_ms": int((_dbg_time.time() - nav_start)*1000)}, "A,E")
                # #endregion
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
            
            logger.info(f"Extracted {len(posts)} posts from {group_name}")
            # #region agent log
            _dbg_log("facebook.py:scrape_group:success", "Successfully extracted posts", {"group_name": group_name, "post_count": len(posts)}, "A")
            # #endregion
            
        except Exception as e:
            logger.error("Error scraping group", group_name=group_name, error=str(e))
            # #region agent log
            _dbg_log("facebook.py:scrape_group:error", "Error scraping group", {"group_name": group_name, "error": str(e), "error_type": type(e).__name__}, "A,B,C,D,E")
            # #endregion
        
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
        
        for group in config.facebook_groups:
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
                logger.warning(
                    "Skipping group - membership pending approval",
                    group_name=group_name
                )
                groups_skipped += 1
            
            elif status in ("failed", "skipped"):
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
