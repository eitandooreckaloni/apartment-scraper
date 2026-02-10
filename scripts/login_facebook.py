#!/usr/bin/env python3
"""Interactive Facebook login script.

Runs browser in headed (visible) mode so you can:
1. Complete any CAPTCHA/verification challenges
2. Log in manually if needed
3. Save the authenticated session for the scraper to use

Usage:
    python scripts/login_facebook.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from src.config import config


async def interactive_login():
    """Run browser in headed mode for manual login/verification."""
    print("=" * 50)
    print("  Facebook Interactive Login")
    print("=" * 50)
    print()
    print("A browser window will open. Please:")
    print("  1. Complete any verification challenges (CAPTCHA, etc.)")
    print("  2. Make sure you're logged into Facebook")
    print("  3. Navigate to one of your groups to verify access")
    print("  4. Press Enter in this terminal when done")
    print()
    
    session_path = config.session_path / "facebook_session.json"
    
    playwright = await async_playwright().start()
    
    # Launch in HEADED mode (visible browser)
    browser = await playwright.firefox.launch(
        headless=False,  # This makes it visible!
        slow_mo=100,  # Slow down actions slightly for human interaction
    )
    
    # Try to load existing session if available
    storage_state = None
    if session_path.exists():
        print(f"Loading existing session from: {session_path}")
        storage_state = str(session_path)
    
    context = await browser.new_context(
        storage_state=storage_state,
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="he-IL",
        timezone_id="Asia/Jerusalem"
    )
    
    page = await context.new_page()
    
    # Navigate to Facebook
    print("\nNavigating to Facebook...")
    await page.goto("https://www.facebook.com")
    
    print("\n" + "=" * 50)
    print("  Browser is now open!")
    print("=" * 50)
    print()
    print("Complete any verification challenges in the browser.")
    print("When you're logged in and can see your feed, press Enter here.")
    print()
    
    # Wait for user input
    input("Press Enter when you're done with verification... ")
    
    # Save the session
    print("\nSaving session...")
    session_path.parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(session_path))
    print(f"Session saved to: {session_path}")
    
    # Close browser
    await browser.close()
    await playwright.stop()
    
    print()
    print("=" * 50)
    print("  Done! You can now run the scraper.")
    print("=" * 50)
    print()
    print("Try running:")
    print("  python scripts/test_scrape_groups.py")
    print()


if __name__ == "__main__":
    asyncio.run(interactive_login())
