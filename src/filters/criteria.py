"""Criteria matching for apartment listings."""

from dataclasses import dataclass, field
from typing import Optional

import structlog

from ..config import config
from ..parser.hybrid import ParsedListing

logger = structlog.get_logger()


@dataclass
class FilterResult:
    """Result of criteria filtering."""
    matches: bool
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0  # 0-1, how well it matches
    bonus_features: list[str] = field(default_factory=list)  # Exciting features found
    has_bonus: bool = False  # Quick check if has any bonus features


def normalize_location(location: str) -> str:
    """Normalize location string for comparison."""
    if not location:
        return ""
    # Remove 'street:' prefix if present
    if location.startswith("street:"):
        location = location[7:]
    return location.lower().strip()


def matches_criteria(listing: ParsedListing) -> FilterResult:
    """Check if a parsed listing matches the configured criteria.
    
    Args:
        listing: Parsed listing to check
    
    Returns:
        FilterResult indicating if listing matches and why/why not
    """
    result = FilterResult(matches=True)
    score_components = []
    
    # Check budget
    if listing.price is not None:
        if listing.price < config.budget_min:
            result.matches = False
            result.reasons.append(f"Price {listing.price} below minimum {config.budget_min}")
        elif listing.price > config.budget_max:
            result.matches = False
            result.reasons.append(f"Price {listing.price} above maximum {config.budget_max}")
        else:
            result.reasons.append(f"Price {listing.price} within budget")
            # Score higher for prices in the middle of range
            range_size = config.budget_max - config.budget_min
            price_from_min = listing.price - config.budget_min
            score_components.append(1.0 - abs(price_from_min / range_size - 0.5))
    else:
        # No price found - could still be relevant
        result.reasons.append("Price not found (might still be relevant)")
        score_components.append(0.5)
    
    # Check rooms
    if listing.rooms is not None:
        if listing.rooms < config.rooms_min:
            result.matches = False
            result.reasons.append(f"Rooms {listing.rooms} below minimum {config.rooms_min}")
        elif listing.rooms > config.rooms_max:
            result.matches = False
            result.reasons.append(f"Rooms {listing.rooms} above maximum {config.rooms_max}")
        else:
            result.reasons.append(f"Rooms {listing.rooms} within range")
            score_components.append(1.0)
    else:
        result.reasons.append("Room count not found")
        score_components.append(0.5)
    
    # Check location
    if listing.location:
        normalized_loc = normalize_location(listing.location)
        location_match = False
        
        for target_loc in config.locations:
            target_normalized = target_loc.lower().strip()
            if target_normalized in normalized_loc or normalized_loc in target_normalized:
                location_match = True
                result.reasons.append(f"Location '{listing.location}' matches target '{target_loc}'")
                score_components.append(1.0)
                break
        
        if not location_match:
            result.matches = False
            result.reasons.append(f"Location '{listing.location}' not in target list")
    else:
        # No location found - might still be relevant
        result.reasons.append("Location not found (might still be relevant)")
        score_components.append(0.3)
    
    # Check listing type (roommates vs whole apartment)
    if listing.is_roommates is not None:
        if config.listing_type == "whole_apartment" and listing.is_roommates:
            result.matches = False
            result.reasons.append("Looking for whole apartment, but this is roommates")
        elif config.listing_type == "roommates" and not listing.is_roommates:
            result.matches = False
            result.reasons.append("Looking for roommates, but this is whole apartment")
        else:
            result.reasons.append(f"Listing type matches preference")
            score_components.append(1.0)
    else:
        result.reasons.append("Listing type not determined")
        score_components.append(0.5)
    
    # Check for bonus features (doesn't affect matching, but boosts score)
    if listing.bonus_features:
        result.bonus_features = listing.bonus_features
        result.has_bonus = True
        result.reasons.append(f"✨ Bonus features found: {', '.join(listing.bonus_features)}")
        # Boost score for listings with bonus features
        score_components.append(1.2)  # Slight boost above 1.0
    
    # Calculate final score
    if score_components:
        result.score = sum(score_components) / len(score_components)
    
    logger.debug(
        "Criteria check complete",
        matches=result.matches,
        score=result.score,
        has_bonus=result.has_bonus,
        bonus_features=result.bonus_features,
        reasons=result.reasons
    )
    
    return result


def should_notify(listing: ParsedListing, filter_result: FilterResult) -> bool:
    """Determine if we should send a notification for this listing.
    
    This adds some fuzzy logic - we might notify for partial matches
    if the listing looks promising.
    """
    # Always notify for full matches
    if filter_result.matches:
        return True
    
    # Consider notifying for high-score partial matches if we're missing data
    if filter_result.score >= 0.7 and not listing.has_minimum_info():
        logger.info("Notifying for partial match due to high score and missing info")
        return True
    
    return False
