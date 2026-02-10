#!/usr/bin/env python3
"""Test script to verify Facebook group scraping and WhatsApp notifications.

This script:
1. Scrapes the configured Facebook groups
2. Sends a WhatsApp message with the first 3 groups and their post counts
3. Stops (does not continue the full scraping workflow)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.scraper.facebook import FacebookScraper
from src.notifier.whatsapp import get_notifier


async def test_scrape_and_notify():
    """Run a test scrape and send WhatsApp summary."""
    print("=" * 50)
    print("  Group Scraping Test")
    print("=" * 50)
    print()
    
    # Initialize scraper
    scraper = FacebookScraper()
    groups_results = []
    
    try:
        await scraper.start()
        
        # Scrape only the first 3 groups (or all if fewer than 3)
        groups_to_scrape = config.facebook_groups[:3]
        print(f"Testing with {len(groups_to_scrape)} groups...")
        print()
        
        for group in groups_to_scrape:
            group_url = group["url"]
            group_name = group["name"]
            
            print(f"Scraping: {group_name}")
            posts = await scraper.scrape_group(group_url, group_name)
            
            groups_results.append({
                "name": group_name,
                "url": group_url,
                "post_count": len(posts),
                "posts": posts[:3]  # Keep first 3 posts for the message
            })
            
            print(f"  Found {len(posts)} posts")
            print()
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.stop()
    
    # Build WhatsApp message
    print()
    print("=" * 50)
    print("  Sending WhatsApp Summary")
    print("=" * 50)
    print()
    
    lines = [
        "🧪 *Facebook Scraping Test Results*",
        "",
        f"Tested {len(groups_results)} groups:",
        ""
    ]
    
    for i, result in enumerate(groups_results, 1):
        # #region agent log
        import json as _json
        from datetime import datetime as _dt
        _debug_log_path = "/Users/eitan/Documents/git-repos/apartment-scraper/.cursor/debug.log"
        _group_name = result['name']
        _formatted_line = f"*{i}. {_group_name}*"
        _has_hebrew = any('\u0590' <= c <= '\u05FF' for c in _group_name)
        with open(_debug_log_path, "a", encoding="utf-8") as _f:
            _f.write(_json.dumps({"hypothesisId": "H1-BiDi", "location": "test_scrape_groups.py:line80", "message": "Formatted group name line", "data": {"group_name": _group_name, "formatted_line": _formatted_line, "has_hebrew": _has_hebrew, "group_name_bytes": _group_name.encode('utf-8').hex(), "formatted_line_bytes": _formatted_line.encode('utf-8').hex()}, "timestamp": int(_dt.now().timestamp() * 1000)}, ensure_ascii=False) + "\n")
        # #endregion
        lines.append(f"*{i}. {result['name']}*")
        lines.append(f"   Posts found: {result['post_count']}")
        
        # Add preview of first post if available
        if result['posts']:
            first_post = result['posts'][0]
            content_preview = first_post.content[:100].replace('\n', ' ')
            if len(first_post.content) > 100:
                content_preview += "..."
            lines.append(f"   Preview: {content_preview}")
        else:
            lines.append("   (No posts found)")
        lines.append("")
    
    total_posts = sum(r["post_count"] for r in groups_results)
    lines.append(f"📊 *Total posts: {total_posts}*")
    lines.append("")
    lines.append("✅ Scraping test complete!")
    
    message = "\n".join(lines)
    
    # #region agent log
    import json as _json
    from datetime import datetime as _dt
    _debug_log_path = "/Users/eitan/Documents/git-repos/apartment-scraper/.cursor/debug.log"
    with open(_debug_log_path, "a", encoding="utf-8") as _f:
        _f.write(_json.dumps({"hypothesisId": "H1-BiDi", "location": "test_scrape_groups.py:before_print", "message": "Full message before print", "data": {"message": message, "message_bytes": message.encode('utf-8').hex()}, "timestamp": int(_dt.now().timestamp() * 1000)}, ensure_ascii=False) + "\n")
    # #endregion
    
    # Print the message we're about to send
    print("Message to send:")
    print("-" * 40)
    print(message)
    print("-" * 40)
    print()
    
    # Send via WhatsApp
    notifier = get_notifier()
    if not notifier.client:
        print("✗ Twilio client not initialized - check credentials")
        return False
    
    try:
        twilio_message = notifier.client.messages.create(
            body=message,
            from_=config.twilio_whatsapp_from,
            to=config.twilio_whatsapp_to
        )
        print(f"✓ WhatsApp message sent! SID: {twilio_message.sid}")
        return True
    except Exception as e:
        print(f"✗ Failed to send WhatsApp: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_scrape_and_notify())
    sys.exit(0 if success else 1)
