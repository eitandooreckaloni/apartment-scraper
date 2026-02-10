"""Main entry point for the apartment scraper."""

import asyncio
import signal
import sys
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import config
from .storage.database import init_db, session_scope
from .storage.dedup import is_duplicate, generate_listing_hash
from .storage.models import Listing, Group
from .scraper.facebook import FacebookScraper, RawPost
from .parser.hybrid import parse_listing
from .filters.criteria import matches_criteria, should_notify
from .notifier.whatsapp import send_listing_notification

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def process_post(post: RawPost) -> bool:
    """Process a single post - parse, filter, and notify if relevant.
    
    Returns True if notification was sent.
    """
    with session_scope() as session:
        # Check for duplicates
        is_dup, existing = is_duplicate(session, post.content, post.post_id)
        if is_dup:
            logger.debug("Skipping duplicate post", post_id=post.post_id)
            return False
        
        # Parse the listing
        parsed = parse_listing(post.content)
        
        # Create listing record
        listing_id = generate_listing_hash(post.content, post.post_id)
        listing = Listing(
            id=listing_id,
            source_group=post.group_name,
            post_url=post.post_url,
            post_id=post.post_id,
            author_name=post.author_name,
            raw_content=post.content,
            parsed_price=parsed.price,
            parsed_location=parsed.location,
            parsed_rooms=parsed.rooms,
            is_roommates=parsed.is_roommates,
            contact_info=parsed.contact_info,
            parse_confidence=parsed.confidence,
            parsed_by=parsed.parsed_by,
            posted_at=post.posted_at,
        )
        listing.images = post.images
        listing.bonus_features = parsed.bonus_features
        
        # Check criteria
        filter_result = matches_criteria(parsed)
        listing.matches_criteria = filter_result.matches
        
        # Save listing
        session.add(listing)
        session.commit()
        
        # Send notification if appropriate
        if should_notify(parsed, filter_result):
            logger.info(
                "Sending notification for matching listing",
                post_id=post.post_id,
                price=parsed.price,
                location=parsed.location
            )
            
            if send_listing_notification(listing, parsed):
                listing.notified = True
                listing.notified_at = datetime.utcnow()
                session.commit()
                return True
        else:
            logger.debug(
                "Listing does not match criteria",
                post_id=post.post_id,
                reasons=filter_result.reasons
            )
    
    return False


async def run_scrape_job():
    """Run a single scrape job."""
    logger.info("Starting scrape job")
    start_time = datetime.utcnow()
    
    scraper = FacebookScraper()
    total_posts = 0
    notifications_sent = 0
    
    try:
        await scraper.start()
        posts = await scraper.scrape_all_groups()
        total_posts = len(posts)
        
        logger.info(f"Scraped {total_posts} posts, processing...")
        
        for post in posts:
            try:
                if await process_post(post):
                    notifications_sent += 1
            except Exception as e:
                logger.error("Error processing post", error=str(e), post_id=post.post_id)
                continue
        
    except Exception as e:
        logger.error("Scrape job failed", error=str(e))
    finally:
        await scraper.stop()
    
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        "Scrape job complete",
        total_posts=total_posts,
        notifications_sent=notifications_sent,
        elapsed_seconds=elapsed
    )


def setup_scheduler() -> AsyncIOScheduler:
    """Set up the job scheduler."""
    scheduler = AsyncIOScheduler()
    
    # Add the scrape job
    scheduler.add_job(
        run_scrape_job,
        trigger=IntervalTrigger(minutes=config.scraper_interval_minutes),
        id="scrape_job",
        name="Facebook Group Scraper",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )
    
    return scheduler


async def main():
    """Main entry point."""
    logger.info("Starting Apartment Scraper")
    logger.info(f"Scrape interval: {config.scraper_interval_minutes} minutes")
    logger.info(f"Budget range: {config.budget_min} - {config.budget_max} NIS")
    logger.info(f"Rooms range: {config.rooms_min} - {config.rooms_max}")
    logger.info(f"Groups to monitor: {len(config.facebook_groups)}")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Set up scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")
    
    # Run initial scrape
    logger.info("Running initial scrape...")
    await run_scrape_job()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        scheduler.shutdown()


def run():
    """Entry point for the application."""
    # Handle signals gracefully
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the async main function
    asyncio.run(main())


if __name__ == "__main__":
    run()
