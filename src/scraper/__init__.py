"""Scraper module with support for multiple data sources."""

from .yad2 import Yad2Scraper, RawPost
from ..config import config


def get_facebook_scraper():
    """
    Factory function to get the appropriate Facebook scraper based on config.
    
    Returns:
        FacebookScraper instance (either library-based or Playwright-based)
    """
    scraper_type = config.facebook_scraper_type
    
    if scraper_type == "playwright":
        from .facebook_playwright import FacebookScraper as PlaywrightScraper
        return PlaywrightScraper()
    else:
        # Default to library-based scraper
        from .facebook import FacebookScraper as LibraryScraper
        return LibraryScraper()


# Default import for backwards compatibility
from .facebook import FacebookScraper

__all__ = ["FacebookScraper", "Yad2Scraper", "RawPost", "get_facebook_scraper"]
