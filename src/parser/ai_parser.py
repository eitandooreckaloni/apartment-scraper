"""AI-powered parser using OpenAI for Hebrew apartment listings."""

import json
from typing import Optional
from dataclasses import dataclass

import structlog
from openai import OpenAI

from ..config import config

logger = structlog.get_logger()


@dataclass
class AIParseResult:
    """Result of AI parsing."""
    price: Optional[int] = None
    location: Optional[str] = None
    rooms: Optional[float] = None
    is_roommates: Optional[bool] = None
    contact_info: Optional[str] = None
    bonus_features: list[str] = None  # Features like rooftop, balcony, big windows
    confidence: float = 0.9  # AI parsing generally high confidence
    summary: Optional[str] = None  # Brief summary of the listing
    
    def __post_init__(self):
        if self.bonus_features is None:
            self.bonus_features = []


SYSTEM_PROMPT = """You are an expert at parsing Hebrew apartment rental listings from Facebook groups in Tel Aviv.

Extract the following information from the listing:
- price: Monthly rent in NIS (Israeli Shekels). Look for numbers with ₪, ש"ח, שקל, or context suggesting rent.
- location: The neighborhood or area in Tel Aviv. Common areas include: פלורנטין, נווה צדק, כרם התימנים, לב העיר, רוטשילד, דיזנגוף, בזל, צפון הישן, צפון חדש, רמת אביב
- rooms: Number of rooms (can be decimal like 2.5 or 3.5)
- is_roommates: true if looking for roommates/subletting a room, false if renting entire apartment
- contact_info: Phone number if present
- bonus_features: Array of special features mentioned. Look for: rooftop/גג, balcony/מרפסת, big windows/חלונות גדולים, terrace/טרסה, penthouse/פנטהאוז, high ceilings, renovated, bright apartment, view
- summary: A brief 1-sentence summary in English

Return ONLY valid JSON with these fields. Use null for fields you can't determine, and [] for bonus_features if none found.

Example output:
{"price": 5500, "location": "florentin", "rooms": 2.5, "is_roommates": false, "contact_info": "0501234567", "bonus_features": ["balcony", "rooftop"], "summary": "2.5 room apartment in Florentin for 5500 NIS with rooftop access"}"""


def parse_with_ai(text: str) -> Optional[AIParseResult]:
    """Parse apartment listing using OpenAI.
    
    Args:
        text: Raw listing text (usually Hebrew)
    
    Returns:
        AIParseResult or None if parsing fails
    """
    if not config.openai_api_key:
        logger.warning("OpenAI API key not configured, skipping AI parsing")
        return None
    
    try:
        client = OpenAI(api_key=config.openai_api_key)
        
        response = client.chat.completions.create(
            model=config.ai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Parse this listing:\n\n{text[:2000]}"}  # Limit text length
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistent parsing
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        data = json.loads(result_text)
        
        result = AIParseResult(
            price=data.get("price"),
            location=data.get("location"),
            rooms=data.get("rooms"),
            is_roommates=data.get("is_roommates"),
            contact_info=data.get("contact_info"),
            bonus_features=data.get("bonus_features", []),
            summary=data.get("summary")
        )
        
        # Calculate confidence based on how many fields were extracted
        fields_found = sum([
            result.price is not None,
            result.location is not None,
            result.rooms is not None,
            result.is_roommates is not None,
        ])
        result.confidence = 0.7 + (fields_found * 0.075)  # 0.7 to 1.0
        
        logger.info(
            "AI parse successful",
            price=result.price,
            location=result.location,
            rooms=result.rooms,
            is_roommates=result.is_roommates,
            confidence=result.confidence
        )
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON", error=str(e))
        return None
        
    except Exception as e:
        logger.error("AI parsing failed", error=str(e))
        return None
