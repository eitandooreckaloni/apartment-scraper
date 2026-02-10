"""Tests for src.parser.regex_parser — all extract_* functions and parse_with_regex."""

import pytest

from src.parser.regex_parser import (
    extract_bonus_features,
    extract_contact_info,
    extract_location,
    extract_price,
    extract_rooms,
    extract_roommates_status,
    parse_with_regex,
)


# ── extract_price ──────────────────────────────────────────────────────────

class TestExtractPrice:
    """Tests for extract_price."""

    def test_shekel_symbol_before(self):
        price, conf = extract_price("השכירות ₪5,000 לחודש")
        assert price == 5000
        assert conf >= 0.85

    def test_shekel_symbol_after(self):
        price, conf = extract_price("5000₪")
        assert price == 5000

    def test_shekel_symbol_with_comma_after(self):
        price, conf = extract_price("7,500₪ לחודש")
        assert price == 7500

    def test_shekels_hebrew_shekel_sign(self):
        price, conf = extract_price('מחיר 6,500 ש"ח')
        assert price == 6500

    def test_shekels_hebrew_shekel_word(self):
        price, conf = extract_price("6500 שקל")
        assert price == 6500

    def test_price_label_hebrew(self):
        price, conf = extract_price("מחיר: 7500")
        assert price == 7500

    def test_rent_label_hebrew(self):
        price, conf = extract_price("שכירות: 5500")
        assert price == 5500

    def test_per_month_suffix(self):
        price, conf = extract_price("4200 לחודש")
        assert price == 4200

    def test_out_of_range_too_low(self):
        price, _ = extract_price("₪500")
        assert price is None

    def test_out_of_range_too_high(self):
        price, _ = extract_price("₪30000")
        assert price is None

    def test_no_price(self):
        price, conf = extract_price("דירה יפה בפלורנטין")
        assert price is None
        assert conf == 0.0

    def test_price_with_dot_separator(self):
        price, _ = extract_price("₪5.000")
        assert price == 5000


# ── extract_rooms ──────────────────────────────────────────────────────────

class TestExtractRooms:
    """Tests for extract_rooms."""

    def test_rooms_hebrew_full(self):
        rooms, conf = extract_rooms("3 חדרים")
        assert rooms == 3.0
        assert conf >= 0.8

    def test_rooms_hebrew_abbreviation(self):
        rooms, _ = extract_rooms("2.5 חד'")
        assert rooms == 2.5

    def test_rooms_with_dira_prefix(self):
        rooms, _ = extract_rooms("דירת 4 חדרים")
        assert rooms == 4.0

    def test_rooms_english(self):
        rooms, _ = extract_rooms("3 rooms available")
        assert rooms == 3.0

    def test_rooms_half(self):
        rooms, _ = extract_rooms("3.5 חדרים")
        assert rooms == 3.5

    def test_no_rooms(self):
        rooms, conf = extract_rooms("דירה יפה במרכז")
        assert rooms is None
        assert conf == 0.0

    def test_rooms_out_of_range(self):
        rooms, _ = extract_rooms("15 חדרים")
        assert rooms is None


# ── extract_location ───────────────────────────────────────────────────────

class TestExtractLocation:
    """Tests for extract_location."""

    def test_florentin_hebrew(self):
        loc, conf = extract_location("דירה בפלורנטין")
        assert loc == "florentin"
        assert conf >= 0.8

    def test_florentin_english(self):
        loc, _ = extract_location("Apartment in Florentin")
        assert loc == "florentin"

    def test_neve_tzedek(self):
        loc, _ = extract_location("נווה צדק, תל אביב")
        assert loc == "neve_tzedek"

    def test_rothschild(self):
        loc, _ = extract_location("שדרות רוטשילד")
        assert loc == "rothschild"

    def test_jaffa(self):
        loc, _ = extract_location("דירה ביפו")
        assert loc == "yaffo"

    def test_street_pattern(self):
        loc, conf = extract_location("רחוב אלנבי 45")
        # Should match the allenby neighborhood
        assert loc == "allenby"

    def test_no_location(self):
        loc, conf = extract_location("דירה יפה 3 חדרים")
        assert loc is None
        assert conf == 0.0


# ── extract_roommates_status ───────────────────────────────────────────────

class TestExtractRoommatesStatus:
    """Tests for extract_roommates_status."""

    def test_roommate_hebrew(self):
        # "שותפים" (plural) uses regular pe (פ) which the regex matches;
        # "שותף" (singular) uses final pe (ף) which is a different codepoint.
        is_rm, conf = extract_roommates_status("מחפשים שותפים לדירה")
        assert is_rm is True
        assert conf >= 0.8

    def test_room_in_apartment(self):
        is_rm, _ = extract_roommates_status("חדר בדירה להשכרה")
        assert is_rm is True

    def test_whole_apartment_hebrew(self):
        is_rm, conf = extract_roommates_status("דירה שלמה להשכרה")
        assert is_rm is False
        assert conf >= 0.8

    def test_whole_apartment_pinu(self):
        is_rm, _ = extract_roommates_status("דירה למסירה")
        assert is_rm is False

    def test_roommate_english(self):
        is_rm, _ = extract_roommates_status("looking for a roommate")
        assert is_rm is True

    def test_whole_english(self):
        is_rm, _ = extract_roommates_status("whole apartment for rent")
        assert is_rm is False

    def test_ambiguous(self):
        is_rm, conf = extract_roommates_status("דירה יפה 5000 שח")
        assert is_rm is None
        assert conf == 0.0


# ── extract_contact_info ──────────────────────────────────────────────────

class TestExtractContactInfo:
    """Tests for extract_contact_info."""

    def test_israeli_mobile_dashes(self):
        phone, conf = extract_contact_info("טלפון: 052-123-4567")
        assert phone == "0521234567"
        assert conf >= 0.9

    def test_israeli_mobile_no_dashes(self):
        phone, _ = extract_contact_info("0501234567")
        assert phone == "0501234567"

    def test_international_format(self):
        phone, _ = extract_contact_info("+972-52-123-4567")
        assert phone == "+972521234567"

    def test_no_phone(self):
        phone, conf = extract_contact_info("דירה בפלורנטין")
        assert phone is None
        assert conf == 0.0


# ── extract_bonus_features ────────────────────────────────────────────────

class TestExtractBonusFeatures:
    """Tests for extract_bonus_features."""

    def test_balcony_hebrew(self, mock_config):
        features = extract_bonus_features("דירה עם מרפסת גדולה")
        assert "balcony" in features

    def test_rooftop_hebrew(self, mock_config):
        features = extract_bonus_features("גישה לגג")
        assert "rooftop" in features

    def test_multiple_features(self, mock_config):
        features = extract_bonus_features("מרפסת, גג, חלונות גדולים")
        assert "balcony" in features
        assert "rooftop" in features
        assert "big windows" in features

    def test_no_features(self, mock_config):
        features = extract_bonus_features("דירה פשוטה")
        assert features == []

    def test_penthouse(self, mock_config):
        features = extract_bonus_features("פנטהאוז מדהים")
        assert "penthouse" in features


# ── parse_with_regex (full pipeline) ──────────────────────────────────────

class TestParseWithRegex:
    """Tests for the combined parse_with_regex function."""

    def test_full_hebrew_listing(self, mock_config, sample_hebrew_listing):
        result = parse_with_regex(sample_hebrew_listing)
        assert result.price == 6500
        assert result.rooms == 3.0
        assert result.location == "florentin"
        assert result.contact_info == "0521234567"
        assert "price" in result.matched_fields
        assert "rooms" in result.matched_fields
        assert "location" in result.matched_fields
        assert result.confidence > 0

    def test_full_english_listing(self, mock_config, sample_english_listing):
        result = parse_with_regex(sample_english_listing)
        assert result.price == 5500
        assert result.rooms == 2.5
        assert result.location == "neve_tzedek"
        assert result.contact_info == "0501234567"

    def test_empty_text(self, mock_config):
        result = parse_with_regex("")
        assert result.price is None
        assert result.rooms is None
        assert result.location is None
        assert result.confidence == 0.0

    def test_confidence_increases_with_fields(self, mock_config):
        result_few = parse_with_regex("5000₪")
        result_many = parse_with_regex(
            "דירת 3 חדרים בפלורנטין ₪5000 להשכרה 0521234567"
        )
        assert result_many.confidence > result_few.confidence
