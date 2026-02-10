"""Yad2 apartment scraper using HTTP requests."""

import asyncio
import random
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import httpx
import structlog

from ..config import config
from ..logging_config import print_status, print_error, print_warning, print_success

logger = structlog.get_logger()


@dataclass
class RawPost:
    """Raw listing data extracted from Yad2.
    
    Compatible with the existing pipeline that expects this structure.
    """
    post_id: str
    content: str
    author_name: Optional[str]
    post_url: str
    images: list[str]
    posted_at: Optional[datetime]
    group_name: str  # Will be "Yad2" or the search category
    group_url: str   # The search URL used


@dataclass
class Yad2Listing:
    """Structured listing data from Yad2 API."""
    listing_id: str
    title: str
    price: Optional[int]
    rooms: Optional[float]
    floor: Optional[int]
    square_meters: Optional[int]
    city: str
    neighborhood: Optional[str]
    street: Optional[str]
    description: str
    images: list[str]
    contact_name: Optional[str]
    date_added: Optional[datetime]
    listing_url: str


class Yad2Scraper:
    """Scrapes apartment listings from Yad2.co.il."""
    
    # Yad2 API endpoints - try multiple possible endpoints
    BASE_URL = "https://www.yad2.co.il"
    API_ENDPOINTS = [
        "https://gw.yad2.co.il/feed-search-legacy/realestate/rent",
        "https://gw.yad2.co.il/legacy-feed-search/realestate/rent", 
        "https://www.yad2.co.il/api/pre-load/getFeedIndex/realestate/rent",
        "https://gw.yad2.co.il/feed/realestate/rent",
    ]
    
    # Common headers to mimic a browser
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.yad2.co.il/realestate/rent",
        "Origin": "https://www.yad2.co.il",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }
    
    # City codes for Yad2
    CITY_CODES = {
        "tel_aviv": 5000,
        "תל אביב": 5000,
        "jerusalem": 3000,
        "ירושלים": 3000,
        "haifa": 4000,
        "חיפה": 4000,
        "beer_sheva": 7100,
        "באר שבע": 7100,
        "ramat_gan": 8600,
        "רמת גן": 8600,
        "herzliya": 6400,
        "הרצליה": 6400,
    }
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
    
    async def _random_delay(self, min_sec: Optional[float] = None, max_sec: Optional[float] = None):
        """Wait a random amount of time to be polite to the server."""
        min_sec = min_sec or config.scraper_min_delay
        max_sec = max_sec or config.scraper_max_delay
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
    
    async def start(self):
        """Initialize the HTTP client."""
        print_status("Starting Yad2 scraper...")
        logger.info("Starting Yad2 scraper")
        
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=30.0,
            follow_redirects=True,
        )
    
    async def stop(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
        print_status("Yad2 scraper stopped")
        logger.info("Yad2 scraper stopped")
    
    def _build_search_params(self) -> dict:
        """Build search parameters dict."""
        params = {}
        
        # City filter
        city_codes = getattr(config, 'yad2_cities', [5000])  # Default to Tel Aviv
        if city_codes:
            params['city'] = city_codes[0]
        
        # Price range
        price_min = getattr(config, 'yad2_price_min', config.budget_min)
        price_max = getattr(config, 'yad2_price_max', config.budget_max)
        if price_min and price_max:
            params['price'] = f"{price_min}-{price_max}"
        
        # Rooms range
        rooms_min = getattr(config, 'yad2_rooms_min', config.rooms_min)
        rooms_max = getattr(config, 'yad2_rooms_max', config.rooms_max)
        if rooms_min and rooms_max:
            params['rooms'] = f"{int(rooms_min)}-{int(rooms_max)}"
        
        # Property type (default to apartment)
        property_type = getattr(config, 'yad2_property_type', None)
        if property_type:
            params['property'] = property_type
        
        return params
    
    def _build_search_url(self, base_url: str) -> str:
        """Build the full search URL with parameters."""
        params = self._build_search_params()
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{query_string}"
    
    def _build_web_url(self) -> str:
        """Build the web page URL for HTML scraping fallback."""
        params = self._build_search_params()
        # Convert to web URL format
        web_params = []
        if 'city' in params:
            web_params.append(f"city={params['city']}")
        if 'price' in params:
            min_p, max_p = params['price'].split('-')
            web_params.append(f"price={min_p}-{max_p}")
        if 'rooms' in params:
            min_r, max_r = params['rooms'].split('-')
            web_params.append(f"rooms={min_r}-{max_r}")
        
        query_string = "&".join(web_params)
        return f"{self.BASE_URL}/realestate/rent?{query_string}"
    
    async def fetch_listings(self) -> list[Yad2Listing]:
        """Fetch listings from Yad2 - try API first, fall back to HTML scraping."""
        if not self.client:
            raise RuntimeError("Scraper not started. Call start() first.")
        
        print_status(f"Fetching listings from Yad2...")
        
        # Try each API endpoint
        for api_base in self.API_ENDPOINTS:
            search_url = self._build_search_url(api_base)
            logger.info("Trying Yad2 API endpoint", url=search_url)
            
            try:
                response = await self.client.get(search_url)
                if response.status_code == 200:
                    data = response.json()
                    listings = self._parse_api_response(data)
                    if listings:
                        print_status(f"  Found {len(listings)} listings via API")
                        logger.info(f"Parsed {len(listings)} listings from Yad2 API")
                        return listings
            except Exception as e:
                logger.debug(f"API endpoint failed: {api_base}", error=str(e))
                continue
        
        # Fall back to HTML scraping
        logger.info("API endpoints failed, falling back to HTML scraping")
        return await self._scrape_html()
    
    def _parse_api_response(self, data: dict) -> list[Yad2Listing]:
        """Parse API response data into listings."""
        listings = []
        feed_items = []
        
        # Try different response structures
        if "data" in data and "feed" in data["data"]:
            feed_items = data["data"]["feed"].get("feed_items", [])
        elif "feed" in data:
            feed_items = data["feed"].get("feed_items", [])
        elif "data" in data:
            data_content = data.get("data", {})
            if isinstance(data_content, dict):
                feed_items = data_content.get("items", data_content.get("feed_items", []))
                # Also check for nested feed structure
                if not feed_items and "feed" in data_content:
                    feed_items = data_content["feed"].get("feed_items", [])
            elif isinstance(data_content, list):
                feed_items = data_content
        
        logger.info(f"Found {len(feed_items)} items in API response")
        
        # Log a sample item to understand structure if parsing fails
        parsed_count = 0
        for item in feed_items:
            try:
                listing = self._parse_listing(item)
                if listing:
                    listings.append(listing)
                    parsed_count += 1
            except Exception as e:
                if parsed_count == 0:
                    # Log first failure with more detail
                    logger.warning("Failed to parse listing", error=str(e), item_keys=list(item.keys()) if isinstance(item, dict) else "not_dict")
                continue
        
        if len(feed_items) > 0 and len(listings) == 0:
            # Log sample of what we got if everything failed
            logger.warning("All items failed to parse", sample_item=str(feed_items[0])[:500] if feed_items else "empty")
        
        return listings
    
    async def _scrape_html(self) -> list[Yad2Listing]:
        """Scrape listings from HTML page as fallback."""
        from bs4 import BeautifulSoup
        import re
        
        web_url = self._build_web_url()
        print_status(f"  Scraping HTML page...")
        logger.info("Scraping Yad2 HTML", url=web_url)
        
        try:
            response = await self.client.get(web_url)
            response.raise_for_status()
            html = response.text
            
            soup = BeautifulSoup(html, 'html.parser')
            listings = []
            
            # Find listing items - Yad2 uses various class patterns
            # Look for links to item pages
            item_links = soup.find_all('a', href=re.compile(r'/realestate/item/'))
            seen_ids = set()
            
            for link in item_links:
                try:
                    href = link.get('href', '')
                    # Extract listing ID from URL
                    match = re.search(r'/item/([a-zA-Z0-9]+)', href)
                    if not match:
                        continue
                    
                    listing_id = match.group(1)
                    if listing_id in seen_ids:
                        continue
                    seen_ids.add(listing_id)
                    
                    # Find the containing card/item element
                    card = link.find_parent('div', recursive=True) or link
                    
                    # Extract price
                    price = None
                    price_el = card.find(string=re.compile(r'₪[\d,]+|[\d,]+\s*₪'))
                    if price_el:
                        price_str = re.sub(r'[^\d]', '', str(price_el))
                        if price_str:
                            price = int(price_str)
                    
                    # Extract title/address from the link text or nearby headers
                    title = ""
                    title_el = card.find(['h2', 'h3', 'h4']) or link
                    if title_el:
                        title = title_el.get_text(strip=True)
                    
                    # Extract rooms if present
                    rooms = None
                    rooms_match = re.search(r'(\d+(?:\.\d)?)\s*חדרים', card.get_text())
                    if rooms_match:
                        rooms = float(rooms_match.group(1))
                    
                    # Extract images
                    images = []
                    img_els = card.find_all('img', src=True)
                    for img in img_els[:3]:
                        src = img.get('src', '')
                        if src and 'placeholder' not in src.lower():
                            images.append(src)
                    
                    listing = Yad2Listing(
                        listing_id=listing_id,
                        title=title,
                        price=price,
                        rooms=rooms,
                        floor=None,
                        square_meters=None,
                        city="",
                        neighborhood="",
                        street="",
                        description="",
                        images=images,
                        contact_name=None,
                        date_added=None,
                        listing_url=f"{self.BASE_URL}{href}" if href.startswith('/') else href,
                    )
                    listings.append(listing)
                    
                except Exception as e:
                    logger.debug("Failed to parse HTML listing", error=str(e))
                    continue
            
            print_status(f"  Found {len(listings)} listings from HTML")
            logger.info(f"Scraped {len(listings)} listings from HTML")
            return listings
            
        except Exception as e:
            print_error(f"HTML scraping failed: {str(e)[:50]}")
            logger.error("HTML scraping failed", error=str(e))
            return []
    
    def _parse_listing(self, item: dict) -> Optional[Yad2Listing]:
        """Parse a single listing from the API response."""
        if not isinstance(item, dict):
            return None
            
        # Skip ads and non-listing items
        item_type = item.get("type", "")
        if item_type in ("ad", "banner", "promotion"):
            return None
        if item.get("is_premium_ad") or item.get("isAd") or item.get("promotional_ad"):
            return None
        
        # Get listing ID from various possible fields
        listing_id = str(
            item.get("id", "") or 
            item.get("token", "") or 
            item.get("link_token", "") or 
            item.get("itemId", "") or
            item.get("ad_number", "")
        )
        if not listing_id:
            return None
        
        # Extract price - check multiple locations
        price = None
        price_raw = item.get("price")
        if price_raw is None:
            # Try to find price in row_4 or other places
            row_4 = item.get("row_4", [])
            if isinstance(row_4, list):
                for r in row_4:
                    if isinstance(r, dict) and r.get("key") == "price":
                        price_raw = r.get("value")
                        break
        
        if isinstance(price_raw, (int, float)):
            price = int(price_raw)
        elif isinstance(price_raw, str):
            price_str = re.sub(r'[^\d]', '', price_raw)
            if price_str:
                price = int(price_str)
        
        # Extract rooms from row_4 structured data
        rooms = None
        floor = None
        square_meters = None
        
        row_4 = item.get("row_4", [])
        if isinstance(row_4, list):
            for r in row_4:
                if isinstance(r, dict):
                    key = r.get("key", "").lower()
                    value = r.get("value")
                    if key == "rooms" or "room" in key:
                        try:
                            rooms = float(value)
                        except (ValueError, TypeError):
                            pass
                    elif key == "floor" or "קומה" in key:
                        try:
                            floor = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif "squar" in key or "meter" in key or "מ" in key:
                        try:
                            square_meters = int(str(value).replace(" ", ""))
                        except (ValueError, TypeError):
                            pass
        
        # Fallback: extract from row_3 if available
        if rooms is None:
            row_3 = item.get("row_3", [])
            if isinstance(row_3, list):
                for r in row_3:
                    if isinstance(r, str) and "חדרים" in r:
                        match = re.search(r'([\d.]+)', r)
                        if match:
                            rooms = float(match.group(1))
                            break
        
        # Extract location from row_2 (format: "דירה, neighborhood, city")
        city = ""
        neighborhood = ""
        street = item.get("row_1", item.get("title_1", ""))
        
        row_2 = item.get("row_2", "")
        if isinstance(row_2, str) and "," in row_2:
            parts = [p.strip() for p in row_2.split(",")]
            if len(parts) >= 3:
                # Format: "property_type, neighborhood, city"
                neighborhood = parts[1]
                city = parts[2]
            elif len(parts) == 2:
                city = parts[1]
        
        # Extract images
        images = []
        images_raw = item.get("images", item.get("images_urls", []))
        if isinstance(images_raw, list):
            for img in images_raw[:5]:  # Limit to 5 images
                if isinstance(img, str):
                    images.append(img)
                elif isinstance(img, dict):
                    img_url = img.get("src", img.get("url", ""))
                    if img_url:
                        images.append(img_url)
        
        # Extract description/title
        title = item.get("title", item.get("row_1", ""))
        if isinstance(title, list):
            title = " ".join(str(t.get("value", t)) if isinstance(t, dict) else str(t) for t in title)
        
        description = item.get("info_text", item.get("description", ""))
        
        # Build listing URL
        listing_url = f"{self.BASE_URL}/realestate/item/{listing_id}"
        
        # Parse date
        date_added = None
        date_raw = item.get("date", item.get("date_added", ""))
        if date_raw:
            try:
                if isinstance(date_raw, str):
                    # Try common formats
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]:
                        try:
                            date_added = datetime.strptime(date_raw.split("T")[0], fmt.split("T")[0])
                            break
                        except ValueError:
                            continue
            except Exception:
                pass
        
        # Extract floor and square meters
        floor = None
        square_meters = None
        
        row_2 = item.get("row_2", [])
        if isinstance(row_2, list):
            for r in row_2:
                if isinstance(r, dict):
                    key = str(r.get("key", "")).lower()
                    value = r.get("value")
                    if "floor" in key or "קומה" in key:
                        try:
                            floor = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif "sqm" in key or "מ\"ר" in key or "meter" in key:
                        try:
                            square_meters = int(value)
                        except (ValueError, TypeError):
                            pass
        
        return Yad2Listing(
            listing_id=listing_id,
            title=title,
            price=price,
            rooms=rooms,
            floor=floor,
            square_meters=square_meters,
            city=city,
            neighborhood=neighborhood or "",
            street=street or "",
            description=description,
            images=images,
            contact_name=item.get("contact_name"),
            date_added=date_added,
            listing_url=listing_url,
        )
    
    def _listing_to_raw_post(self, listing: Yad2Listing) -> RawPost:
        """Convert a Yad2Listing to a RawPost for compatibility with existing pipeline."""
        # Build content string similar to what we'd get from a Facebook post
        content_parts = []
        
        if listing.title:
            content_parts.append(listing.title)
        
        if listing.price:
            content_parts.append(f"מחיר: {listing.price:,} ₪")
        
        if listing.rooms:
            content_parts.append(f"חדרים: {listing.rooms}")
        
        location_parts = []
        if listing.neighborhood:
            location_parts.append(listing.neighborhood)
        if listing.city:
            location_parts.append(listing.city)
        if location_parts:
            content_parts.append(f"מיקום: {', '.join(location_parts)}")
        
        if listing.street:
            content_parts.append(f"רחוב: {listing.street}")
        
        if listing.floor is not None:
            content_parts.append(f"קומה: {listing.floor}")
        
        if listing.square_meters:
            content_parts.append(f"גודל: {listing.square_meters} מ\"ר")
        
        if listing.description:
            content_parts.append(f"\n{listing.description}")
        
        content = "\n".join(content_parts)
        
        return RawPost(
            post_id=listing.listing_id,
            content=content,
            author_name=listing.contact_name,
            post_url=listing.listing_url,
            images=listing.images,
            posted_at=listing.date_added,
            group_name="Yad2",
            group_url=self._build_web_url(),
        )
    
    async def scrape_listings(self) -> list[RawPost]:
        """Main method: fetch and convert listings to RawPost format."""
        listings = await self.fetch_listings()
        
        posts = []
        for listing in listings:
            post = self._listing_to_raw_post(listing)
            posts.append(post)
        
        return posts
    
    async def scrape_all(self) -> list[RawPost]:
        """Alias for scrape_listings() to match FacebookScraper interface."""
        return await self.scrape_listings()


async def run_scraper() -> list[RawPost]:
    """Convenience function to run the scraper."""
    scraper = Yad2Scraper()
    try:
        await scraper.start()
        posts = await scraper.scrape_listings()
        return posts
    finally:
        await scraper.stop()
