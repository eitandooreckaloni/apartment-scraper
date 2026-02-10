"""Deduplication logic for apartment listings."""

import hashlib
import re
from typing import Optional

from fuzzywuzzy import fuzz
from sqlalchemy.orm import Session

from .models import Listing


def normalize_text(text: str) -> str:
    """Normalize text for comparison - remove extra whitespace, emojis, etc."""
    # Remove emojis and special characters
    text = re.sub(r'[^\w\s\u0590-\u05FF]', ' ', text)  # Keep Hebrew chars
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.lower().strip()


def generate_listing_hash(content: str, post_id: Optional[str] = None) -> str:
    """Generate a unique hash for a listing.
    
    Uses post_id if available (most reliable), otherwise hashes normalized content.
    """
    if post_id:
        # If we have a post ID, use it as the primary identifier
        return hashlib.sha256(f"post:{post_id}".encode()).hexdigest()
    
    # Fall back to content hash
    normalized = normalize_text(content)
    return hashlib.sha256(normalized.encode()).hexdigest()


def is_duplicate(
    session: Session,
    content: str,
    post_id: Optional[str] = None,
    similarity_threshold: int = 85
) -> tuple[bool, Optional[Listing]]:
    """Check if a listing is a duplicate.
    
    Args:
        session: Database session
        content: Raw listing content
        post_id: Facebook post ID if available
        similarity_threshold: Fuzzy match threshold (0-100)
    
    Returns:
        Tuple of (is_duplicate, existing_listing or None)
    """
    # First, check for exact hash match
    listing_hash = generate_listing_hash(content, post_id)
    existing = session.query(Listing).filter(Listing.id == listing_hash).first()
    if existing:
        return True, existing
    
    # If we have a post_id, also check by post_id directly
    if post_id:
        existing = session.query(Listing).filter(Listing.post_id == post_id).first()
        if existing:
            return True, existing
    
    # Check for similar content using fuzzy matching
    # Only check recent listings (last 7 days) to keep it fast
    normalized_content = normalize_text(content)
    
    # Get recent listings for fuzzy comparison
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_listings = session.query(Listing).filter(
        Listing.scraped_at >= week_ago
    ).all()
    
    for listing in recent_listings:
        existing_normalized = normalize_text(listing.raw_content)
        similarity = fuzz.ratio(normalized_content, existing_normalized)
        if similarity >= similarity_threshold:
            return True, listing
    
    return False, None


def mark_as_seen(
    session: Session,
    listing_id: str,
    content: str,
    source_group: str,
    post_url: str,
    post_id: str,
    **kwargs
) -> Listing:
    """Create a new listing record."""
    listing = Listing(
        id=listing_id,
        raw_content=content,
        source_group=source_group,
        post_url=post_url,
        post_id=post_id,
        **kwargs
    )
    session.add(listing)
    return listing
