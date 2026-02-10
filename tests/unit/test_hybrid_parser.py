"""Tests for src.parser.hybrid — merge_results and ParsedListing."""

import pytest

from src.parser.hybrid import ParsedListing, merge_results
from src.parser.regex_parser import RegexParseResult
from src.parser.ai_parser import AIParseResult


# ── ParsedListing ─────────────────────────────────────────────────────────

class TestParsedListing:
    """Tests for the ParsedListing dataclass."""

    def test_has_minimum_info_with_price(self):
        pl = ParsedListing(price=5000)
        assert pl.has_minimum_info() is True

    def test_has_minimum_info_with_location_and_rooms(self):
        pl = ParsedListing(location="florentin", rooms=3)
        assert pl.has_minimum_info() is True

    def test_has_minimum_info_missing_everything(self):
        pl = ParsedListing()
        assert pl.has_minimum_info() is False

    def test_has_minimum_info_only_location(self):
        pl = ParsedListing(location="florentin")
        assert pl.has_minimum_info() is False

    def test_has_minimum_info_only_rooms(self):
        pl = ParsedListing(rooms=2.5)
        assert pl.has_minimum_info() is False

    def test_has_bonus_features_true(self):
        pl = ParsedListing(bonus_features=["rooftop"])
        assert pl.has_bonus_features() is True

    def test_has_bonus_features_false(self):
        pl = ParsedListing()
        assert pl.has_bonus_features() is False


# ── merge_results ─────────────────────────────────────────────────────────

class TestMergeResults:
    """Tests for merge_results."""

    def test_regex_only(self):
        regex = RegexParseResult(
            price=5000,
            location="florentin",
            rooms=3.0,
            is_roommates=False,
            confidence=0.9,
            matched_fields=["price", "location", "rooms", "is_roommates"],
        )
        merged = merge_results(regex, None)
        assert merged.price == 5000
        assert merged.location == "florentin"
        assert merged.rooms == 3.0
        assert merged.is_roommates is False
        assert merged.parsed_by == "regex"
        assert merged.confidence == 0.9

    def test_ai_fills_gaps(self):
        regex = RegexParseResult(
            price=5000,
            confidence=0.4,
            matched_fields=["price"],
        )
        ai = AIParseResult(
            price=5000,
            location="neve_tzedek",
            rooms=2.5,
            is_roommates=False,
            confidence=0.85,
            summary="Nice apartment",
        )
        merged = merge_results(regex, ai)

        # Price comes from regex (already set)
        assert merged.price == 5000
        # AI fills the missing fields
        assert merged.location == "neve_tzedek"
        assert merged.rooms == 2.5
        assert merged.is_roommates is False
        assert merged.summary == "Nice apartment"
        # Low regex confidence → parsed_by should be "ai"
        assert merged.parsed_by == "ai"

    def test_regex_takes_precedence_when_both_found(self):
        regex = RegexParseResult(
            price=6000,
            location="rothschild",
            rooms=3.0,
            confidence=0.8,
            matched_fields=["price", "location", "rooms"],
        )
        ai = AIParseResult(
            price=5500,   # AI disagrees, but regex had it first
            location="florentin",
            rooms=2.5,
            confidence=0.85,
        )
        merged = merge_results(regex, ai)
        # Regex values should win because they were already set
        assert merged.price == 6000
        assert merged.location == "rothschild"
        assert merged.rooms == 3.0
        assert merged.parsed_by == "hybrid"

    def test_bonus_features_merged_and_deduplicated(self):
        regex = RegexParseResult(
            bonus_features=["rooftop", "balcony"],
            confidence=0.5,
            matched_fields=["bonus_features"],
        )
        ai = AIParseResult(
            bonus_features=["balcony", "penthouse"],  # "balcony" duplicate
            confidence=0.8,
        )
        merged = merge_results(regex, ai)
        lower_features = [f.lower() for f in merged.bonus_features]
        assert "rooftop" in lower_features
        assert "balcony" in lower_features
        assert "penthouse" in lower_features
        assert len(merged.bonus_features) == 3  # no duplication

    def test_confidence_uses_ai_when_regex_low(self):
        regex = RegexParseResult(confidence=0.3, matched_fields=[])
        ai = AIParseResult(confidence=0.9)
        merged = merge_results(regex, ai)
        assert merged.confidence == 0.9

    def test_confidence_uses_max_when_regex_high(self):
        regex = RegexParseResult(confidence=0.7, matched_fields=["price"])
        ai = AIParseResult(confidence=0.85)
        merged = merge_results(regex, ai)
        assert merged.confidence == 0.85  # max(0.7, 0.85)
