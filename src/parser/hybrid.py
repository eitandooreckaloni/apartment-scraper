"""Hybrid parser that combines regex and AI parsing."""

from dataclasses import dataclass
from typing import Optional

import structlog

from ..config import config
from .regex_parser import parse_with_regex, RegexParseResult
from .ai_parser import parse_with_ai, AIParseResult

logger = structlog.get_logger()


@dataclass
class ParsedListing:
    """Final parsed listing result."""
    price: Optional[int] = None
    location: Optional[str] = None
    rooms: Optional[float] = None
    is_roommates: Optional[bool] = None
    contact_info: Optional[str] = None
    confidence: float = 0.0
    parsed_by: str = "unknown"  # 'regex', 'ai', or 'hybrid'
    summary: Optional[str] = None
    
    def has_minimum_info(self) -> bool:
        """Check if we have enough info to consider this a valid listing."""
        # Need at least price or (location and rooms)
        return self.price is not None or (self.location is not None and self.rooms is not None)


def merge_results(regex_result: RegexParseResult, ai_result: Optional[AIParseResult]) -> ParsedListing:
    """Merge regex and AI results, preferring higher-confidence values."""
    result = ParsedListing()
    
    # Start with regex results
    result.price = regex_result.price
    result.location = regex_result.location
    result.rooms = regex_result.rooms
    result.is_roommates = regex_result.is_roommates
    result.contact_info = regex_result.contact_info
    result.confidence = regex_result.confidence
    result.parsed_by = "regex"
    
    # Override with AI results where regex didn't find anything
    if ai_result:
        if result.price is None and ai_result.price:
            result.price = ai_result.price
        if result.location is None and ai_result.location:
            result.location = ai_result.location
        if result.rooms is None and ai_result.rooms:
            result.rooms = ai_result.rooms
        if result.is_roommates is None and ai_result.is_roommates is not None:
            result.is_roommates = ai_result.is_roommates
        if result.contact_info is None and ai_result.contact_info:
            result.contact_info = ai_result.contact_info
        
        result.summary = ai_result.summary
        
        # Update confidence and parsed_by
        if regex_result.confidence < 0.5:
            result.confidence = ai_result.confidence
            result.parsed_by = "ai"
        else:
            result.confidence = max(regex_result.confidence, ai_result.confidence)
            result.parsed_by = "hybrid"
    
    return result


def parse_listing(text: str) -> ParsedListing:
    """Parse an apartment listing using hybrid approach.
    
    Strategy:
    1. Always try regex first (fast and free)
    2. If regex confidence is below threshold AND AI is enabled, use AI
    3. Merge results, preferring regex for high-confidence fields
    
    Args:
        text: Raw listing text
    
    Returns:
        ParsedListing with extracted information
    """
    # Step 1: Regex parsing
    regex_result = parse_with_regex(text)
    
    logger.debug(
        "Regex parsing complete",
        confidence=regex_result.confidence,
        matched_fields=regex_result.matched_fields
    )
    
    # Step 2: Determine if we need AI
    needs_ai = (
        config.use_ai_fallback and
        regex_result.confidence < config.regex_confidence_threshold
    )
    
    ai_result = None
    if needs_ai:
        logger.info("Regex confidence low, using AI fallback")
        ai_result = parse_with_ai(text)
    
    # Step 3: Merge results
    final_result = merge_results(regex_result, ai_result)
    
    logger.info(
        "Parsing complete",
        price=final_result.price,
        location=final_result.location,
        rooms=final_result.rooms,
        is_roommates=final_result.is_roommates,
        confidence=final_result.confidence,
        parsed_by=final_result.parsed_by
    )
    
    return final_result
