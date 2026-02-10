"""Tests for src.filters.criteria — matches_criteria, should_notify, normalize_location."""

import pytest

from src.filters.criteria import FilterResult, matches_criteria, normalize_location, should_notify
from src.parser.hybrid import ParsedListing


# ── normalize_location ────────────────────────────────────────────────────

class TestNormalizeLocation:

    def test_strips_street_prefix(self):
        assert normalize_location("street:allenby") == "allenby"

    def test_lowercases(self):
        assert normalize_location("Florentin") == "florentin"

    def test_strips_whitespace(self):
        assert normalize_location("  rothschild  ") == "rothschild"

    def test_empty_string(self):
        assert normalize_location("") == ""

    def test_none_like(self):
        # normalize_location guards with `if not location`
        assert normalize_location("") == ""


# ── matches_criteria ──────────────────────────────────────────────────────

class TestMatchesCriteria:

    def test_perfect_match(self, mock_config):
        listing = ParsedListing(
            price=6000,
            location="florentin",
            rooms=3.0,
            is_roommates=False,
        )
        result = matches_criteria(listing)
        assert result.matches is True
        assert result.score > 0

    def test_price_below_min(self, mock_config):
        listing = ParsedListing(price=2000, location="florentin", rooms=3.0)
        result = matches_criteria(listing)
        assert result.matches is False
        assert any("below minimum" in r for r in result.reasons)

    def test_price_above_max(self, mock_config):
        listing = ParsedListing(price=15000, location="florentin", rooms=3.0)
        result = matches_criteria(listing)
        assert result.matches is False
        assert any("above maximum" in r for r in result.reasons)

    def test_rooms_below_min(self, mock_config):
        listing = ParsedListing(price=6000, location="florentin", rooms=1.0)
        result = matches_criteria(listing)
        assert result.matches is False
        assert any("below minimum" in r for r in result.reasons)

    def test_rooms_above_max(self, mock_config):
        listing = ParsedListing(price=6000, location="florentin", rooms=6.0)
        result = matches_criteria(listing)
        assert result.matches is False
        assert any("above maximum" in r for r in result.reasons)

    def test_location_mismatch(self, mock_config):
        listing = ParsedListing(price=6000, location="ramat_aviv", rooms=3.0)
        result = matches_criteria(listing)
        assert result.matches is False
        assert any("not in target list" in r for r in result.reasons)

    def test_roommates_when_want_whole(self, mock_config):
        listing = ParsedListing(
            price=6000,
            location="florentin",
            rooms=3.0,
            is_roommates=True,
        )
        result = matches_criteria(listing)
        assert result.matches is False
        assert any("roommates" in r.lower() for r in result.reasons)

    def test_missing_price_still_may_match(self, mock_config):
        listing = ParsedListing(location="florentin", rooms=3.0, is_roommates=False)
        result = matches_criteria(listing)
        # No price -> "might still be relevant", doesn't cause rejection
        assert result.matches is True

    def test_missing_location_still_may_match(self, mock_config):
        listing = ParsedListing(price=6000, rooms=3.0, is_roommates=False)
        result = matches_criteria(listing)
        assert result.matches is True

    def test_bonus_features_recorded(self, mock_config):
        listing = ParsedListing(
            price=6000,
            location="florentin",
            rooms=3.0,
            is_roommates=False,
            bonus_features=["rooftop", "balcony"],
        )
        result = matches_criteria(listing)
        assert result.has_bonus is True
        assert "rooftop" in result.bonus_features


# ── should_notify ─────────────────────────────────────────────────────────

class TestShouldNotify:

    def test_full_match_notifies(self, mock_config):
        listing = ParsedListing(price=6000, location="florentin", rooms=3.0)
        fr = FilterResult(matches=True, score=0.9)
        assert should_notify(listing, fr) is True

    def test_no_match_low_score_does_not_notify(self, mock_config):
        listing = ParsedListing(price=6000, location="florentin", rooms=3.0)
        fr = FilterResult(matches=False, score=0.3)
        assert should_notify(listing, fr) is False

    def test_high_score_partial_match_with_missing_info(self, mock_config):
        # Missing enough info that has_minimum_info() is False
        listing = ParsedListing()
        fr = FilterResult(matches=False, score=0.75)
        assert should_notify(listing, fr) is True

    def test_high_score_but_has_full_info_does_not_notify(self, mock_config):
        listing = ParsedListing(price=6000, location="florentin", rooms=3.0)
        fr = FilterResult(matches=False, score=0.75)
        # has_minimum_info() is True, so even with high score, no notify
        assert should_notify(listing, fr) is False
