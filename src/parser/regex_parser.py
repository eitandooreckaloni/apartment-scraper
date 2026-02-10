"""Regex-based parser for Hebrew apartment listings."""

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


# Tel Aviv neighborhoods - Hebrew and English
NEIGHBORHOODS = {
    # Central Tel Aviv
    "florentin": ["florentin", "פלורנטין"],
    "neve_tzedek": ["neve tzedek", "נווה צדק", "נוה צדק"],
    "kerem_hatemanim": ["kerem hatemanim", "כרם התימנים", "כרם תימנים"],
    "lev_hair": ["lev hair", "לב העיר", "לב תל אביב", "מרכז העיר"],
    "rothschild": ["rothschild", "רוטשילד", "שדרות רוטשילד"],
    "dizengoff": ["dizengoff", "דיזנגוף"],
    "basel": ["basel", "בזל", "כיכר בזל"],
    "habima": ["habima", "הבימה"],
    "allenby": ["allenby", "אלנבי"],
    
    # North Tel Aviv
    "old_north": ["old north", "צפון הישן", "הצפון הישן"],
    "new_north": ["new north", "צפון חדש", "הצפון החדש"],
    "ramat_aviv": ["ramat aviv", "רמת אביב"],
    "bavli": ["bavli", "בבלי"],
    "yarkon": ["yarkon", "הירקון", "פארק הירקון"],
    
    # South Tel Aviv
    "shapira": ["shapira", "שפירא"],
    "neve_shaanan": ["neve shaanan", "נווה שאנן"],
    "hatikva": ["hatikva", "התקווה", "שכונת התקווה"],
    
    # Beach areas
    "tel_aviv_port": ["namal", "נמל", "נמל תל אביב", "port"],
    "gordon_beach": ["gordon", "גורדון"],
    "frishman": ["frishman", "פרישמן"],
    
    # Other
    "yaffo": ["jaffa", "yafo", "יפו"],
    "bat_yam": ["bat yam", "בת ים"],
    "givatayim": ["givatayim", "גבעתיים"],
    "ramat_gan": ["ramat gan", "רמת גן"],
}


@dataclass
class RegexParseResult:
    """Result of regex parsing."""
    price: Optional[int] = None
    location: Optional[str] = None
    rooms: Optional[float] = None
    is_roommates: Optional[bool] = None
    contact_info: Optional[str] = None
    confidence: float = 0.0
    matched_fields: list[str] = field(default_factory=list)


def extract_price(text: str) -> tuple[Optional[int], float]:
    """Extract price from text.
    
    Returns (price, confidence).
    """
    patterns = [
        # ₪5,000 or ₪5000
        r'₪\s*([0-9]{1,2}[,.]?[0-9]{3})',
        # 5,000₪ or 5000₪
        r'([0-9]{1,2}[,.]?[0-9]{3})\s*₪',
        # 5,000 ש"ח or שח or שקל
        r'([0-9]{1,2}[,.]?[0-9]{3})\s*(?:ש"ח|שח|שקל|ש״ח)',
        # Price with לחודש (per month)
        r'([0-9]{1,2}[,.]?[0-9]{3})\s*(?:לחודש|לחו\'|/חודש)',
        # מחיר: 5000 (Price: 5000)
        r'מחיר[:\s]+([0-9]{1,2}[,.]?[0-9]{3})',
        # שכירות: 5000 (Rent: 5000)
        r'שכירות[:\s]+([0-9]{1,2}[,.]?[0-9]{3})',
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).replace(',', '').replace('.', '')
            try:
                price = int(price_str)
                # Sanity check - typical Tel Aviv rent range
                if 1500 <= price <= 25000:
                    # Higher confidence for explicit patterns
                    confidence = 0.95 if i < 4 else 0.85
                    return price, confidence
            except ValueError:
                continue
    
    return None, 0.0


def extract_rooms(text: str) -> tuple[Optional[float], float]:
    """Extract number of rooms from text."""
    patterns = [
        # 3 חדרים or 3חדרים
        r'([0-9]+(?:[.,][0-9])?)\s*חדרים',
        # 3 חד' or 3חד
        r'([0-9]+(?:[.,][0-9])?)\s*חד[\'׳]?',
        # דירת 3 חדרים
        r'דירת?\s*([0-9]+(?:[.,][0-9])?)\s*חד',
        # 3 rooms
        r'([0-9]+(?:[.,][0-9])?)\s*rooms?',
        # Just a number followed by ח (common abbreviation)
        r'([0-9]+(?:[.,][0-9])?)\s*ח\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            rooms_str = match.group(1).replace(',', '.')
            try:
                rooms = float(rooms_str)
                if 1 <= rooms <= 10:  # Sanity check
                    return rooms, 0.9
            except ValueError:
                continue
    
    return None, 0.0


def extract_location(text: str) -> tuple[Optional[str], float]:
    """Extract location/neighborhood from text."""
    text_lower = text.lower()
    
    for location_key, aliases in NEIGHBORHOODS.items():
        for alias in aliases:
            if alias.lower() in text_lower:
                return location_key, 0.9
    
    # Check for street names with common Tel Aviv streets
    street_patterns = [
        r'רחוב\s+([א-ת\s]+)',
        r'רח[\'׳]\s+([א-ת\s]+)',
        r'street\s+(\w+)',
    ]
    
    for pattern in street_patterns:
        match = re.search(pattern, text)
        if match:
            street = match.group(1).strip()
            if len(street) > 2:
                return f"street:{street}", 0.6
    
    return None, 0.0


def extract_roommates_status(text: str) -> tuple[Optional[bool], float]:
    """Determine if listing is for roommates or whole apartment."""
    
    # Roommates indicators
    roommate_patterns = [
        r'שותפ',  # שותף, שותפים, שותפה
        r'חדר\s+בדירה',
        r'חדר\s+להשכרה',
        r'מחפש(?:ת|ים)?\s+שותפ',
        r'roommate',
        r'looking\s+for\s+(?:a\s+)?room',
    ]
    
    # Whole apartment indicators
    whole_apt_patterns = [
        r'דירה\s+(?:שלמה|להשכרה|ל?מסירה)',
        r'דירת\s+[0-9]+\s+חדרים?\s+להשכרה',
        r'whole\s+apartment',
        r'entire\s+(?:apartment|flat)',
        r'למסירה',
        r'פינוי',
    ]
    
    text_lower = text.lower()
    
    for pattern in roommate_patterns:
        if re.search(pattern, text_lower):
            return True, 0.85
    
    for pattern in whole_apt_patterns:
        if re.search(pattern, text_lower):
            return False, 0.85
    
    return None, 0.0


def extract_contact_info(text: str) -> tuple[Optional[str], float]:
    """Extract phone number or contact info."""
    # Israeli phone patterns
    patterns = [
        r'0[5][0-9]{1}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',  # 05X-XXX-XXXX
        r'0[5][0-9]{8}',  # 05XXXXXXXX
        r'\+972[-.\s]?5[0-9][-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',  # +972-5X-XXX-XXXX
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r'[-.\s]', '', match.group())
            return phone, 0.95
    
    return None, 0.0


def parse_with_regex(text: str) -> RegexParseResult:
    """Parse apartment listing using regex patterns.
    
    Returns parsed fields and overall confidence.
    """
    result = RegexParseResult()
    confidences = []
    
    # Extract each field
    price, price_conf = extract_price(text)
    if price:
        result.price = price
        result.matched_fields.append("price")
        confidences.append(price_conf)
    
    rooms, rooms_conf = extract_rooms(text)
    if rooms:
        result.rooms = rooms
        result.matched_fields.append("rooms")
        confidences.append(rooms_conf)
    
    location, loc_conf = extract_location(text)
    if location:
        result.location = location
        result.matched_fields.append("location")
        confidences.append(loc_conf)
    
    is_roommates, roommates_conf = extract_roommates_status(text)
    if is_roommates is not None:
        result.is_roommates = is_roommates
        result.matched_fields.append("is_roommates")
        confidences.append(roommates_conf)
    
    contact, contact_conf = extract_contact_info(text)
    if contact:
        result.contact_info = contact
        result.matched_fields.append("contact")
        confidences.append(contact_conf)
    
    # Calculate overall confidence
    if confidences:
        # Weight by number of fields matched
        field_coverage = len(result.matched_fields) / 4  # 4 key fields (excluding contact)
        avg_confidence = sum(confidences) / len(confidences)
        result.confidence = (avg_confidence * 0.6) + (field_coverage * 0.4)
    
    logger.debug(
        "Regex parse result",
        matched_fields=result.matched_fields,
        confidence=result.confidence
    )
    
    return result
