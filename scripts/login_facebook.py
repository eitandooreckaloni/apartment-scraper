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
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from src.config import config


def convert_playwright_cookies_to_netscape(storage_state: dict, output_path: Path):
    """
    Convert Playwright storage state cookies to Netscape cookie format.
    
    The facebook_scraper library can read cookies in Netscape format (like from browser export).
    """
    cookies = storage_state.get("cookies", [])
    
    # Convert to format expected by facebook_scraper
    # facebook_scraper accepts a JSON file with cookies in this format
    converted = []
    for cookie in cookies:
        # Filter to only Facebook cookies
        domain = cookie.get("domain", "")
        if "facebook.com" not in domain:
            continue
        
        converted.append({
            "name": cookie.get("name"),
            "value": cookie.get("value"),
            "domain": domain,
            "path": cookie.get("path", "/"),
            "expires": cookie.get("expires", -1),
            "httpOnly": cookie.get("httpOnly", False),
            "secure": cookie.get("secure", True),
            "sameSite": cookie.get("sameSite", "None"),
        })
    
    # Save in JSON format that facebook_scraper can read
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2)
    
    return len(converted)


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
    cookies_path = config.session_path / "facebook_cookies.json"
    
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
    
    # Get storage state as dict for processing
    storage_state_data = await context.storage_state()
    
    # Save Playwright session (for playwright scraper)
    await context.storage_state(path=str(session_path))
    print(f"  Playwright session saved to: {session_path}")
    
    # Convert and save cookies for facebook_scraper library
    num_cookies = convert_playwright_cookies_to_netscape(storage_state_data, cookies_path)
    print(f"  Library cookies saved to: {cookies_path} ({num_cookies} cookies)")
    
    # Close browser
    await browser.close()
    await playwright.stop()
    
    print()
    print("=" * 50)
    print("  Done! You can now run the scraper.")
    print("=" * 50)
    print()
    print("Both scraper types are now configured:")
    print(f"  - Playwright: {session_path}")
    print(f"  - Library:    {cookies_path}")
    print()
    print("To change scraper type, edit config.yaml:")
    print('  facebook.scraper_type: "library"   # or "playwright"')
    print()


if __name__ == "__main__":
    asyncio.run(interactive_login())
