#!/usr/bin/env python3
"""Test script to verify Yad2 scraping and WhatsApp notifications.

This script:
1. Scrapes listings from Yad2
2. Sends a WhatsApp message with the results summary
3. Stops (does not continue the full scraping workflow)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.scraper.yad2 import Yad2Scraper
from src.notifier.whatsapp import get_notifier


async def test_scrape_and_notify():
    """Run a test scrape and send WhatsApp summary."""
    print("=" * 50)
    print("  Yad2 Scraping Test")
    print("=" * 50)
    print()
    
    # Show search parameters
    print(f"Search parameters:")
    print(f"  Cities: {config.yad2_cities}")
    print(f"  Price: {config.yad2_price_min:,} - {config.yad2_price_max:,} NIS")
    print(f"  Rooms: {config.yad2_rooms_min} - {config.yad2_rooms_max}")
    print()
    
    # Initialize scraper
    scraper = Yad2Scraper()
    listings = []
    
    try:
        await scraper.start()
        listings = await scraper.scrape_listings()
        print(f"\nFound {len(listings)} listings")
        
        # Show first few listings
        if listings:
            print("\nSample listings:")
            print("-" * 40)
            for i, listing in enumerate(listings[:5], 1):
                # Parse some info from content
                lines = listing.content.split('\n')
                title = lines[0] if lines else "No title"
                print(f"\n{i}. {title[:60]}...")
                print(f"   URL: {listing.post_url}")
                if listing.images:
                    print(f"   Images: {len(listing.images)}")
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
        "🏠 *Yad2 Scraping Test Results*",
        "",
        f"Search: Tel Aviv, {config.yad2_price_min:,}-{config.yad2_price_max:,} NIS, {config.yad2_rooms_min}-{config.yad2_rooms_max} rooms",
        "",
        f"📊 *Found {len(listings)} listings*",
        "",
    ]
    
    # Add sample listings
    if listings:
        lines.append("Sample listings:")
        for i, listing in enumerate(listings[:3], 1):
            content_lines = listing.content.split('\n')
            title = content_lines[0][:50] if content_lines else "?"
            lines.append(f"{i}. {title}")
            lines.append(f"   {listing.post_url}")
        lines.append("")
    
    lines.append("✅ Scraping test complete!")
    
    message = "\n".join(lines)
    
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
