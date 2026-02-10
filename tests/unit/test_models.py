"""Tests for src.storage.models — Listing property round-trips."""

import pytest

from src.storage.models import Listing


class TestListingImages:
    """Test the Listing.images JSON-backed property."""

    def test_set_and_get_images(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        listing.images = ["img1.jpg", "img2.jpg"]
        assert listing.images == ["img1.jpg", "img2.jpg"]

    def test_empty_images_default(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        assert listing.images == []

    def test_set_none_images(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        listing.images = []
        assert listing.images == []

    def test_set_then_clear_images(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        listing.images = ["a.jpg"]
        listing.images = []
        assert listing.images == []


class TestListingBonusFeatures:
    """Test the Listing.bonus_features JSON-backed property."""

    def test_set_and_get_features(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        listing.bonus_features = ["rooftop", "balcony"]
        assert listing.bonus_features == ["rooftop", "balcony"]

    def test_empty_features_default(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        assert listing.bonus_features == []

    def test_has_bonus_features(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        listing.bonus_features = ["penthouse"]
        assert listing.has_bonus_features() is True

    def test_has_bonus_features_empty(self):
        listing = Listing(
            id="test123",
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
        )
        assert listing.has_bonus_features() is False


class TestListingRepr:
    """Test __repr__."""

    def test_repr_format(self):
        listing = Listing(
            id="abcdef1234567890" * 4,
            source_group="test",
            post_url="https://example.com",
            post_id="p1",
            raw_content="hello",
            parsed_price=5000,
            parsed_location="florentin",
        )
        r = repr(listing)
        assert "5000" in r
        assert "florentin" in r
