"""Tests for src.storage.dedup — normalize_text and generate_listing_hash."""

import pytest

from src.storage.dedup import generate_listing_hash, normalize_text


# ── normalize_text ────────────────────────────────────────────────────────

class TestNormalizeText:

    def test_lowercases(self):
        assert normalize_text("Hello World") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_text("hello   world\n\nnew") == "hello world new"

    def test_removes_emojis(self):
        result = normalize_text("🏠 דירה יפה 🌟")
        # Hebrew characters should be preserved; emojis replaced by space
        assert "דירה" in result
        assert "יפה" in result
        assert "🏠" not in result

    def test_preserves_hebrew(self):
        result = normalize_text("דירת 3 חדרים בפלורנטין")
        assert "דירת" in result
        assert "פלורנטין" in result

    def test_strips(self):
        assert normalize_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_text("") == ""


# ── generate_listing_hash ─────────────────────────────────────────────────

class TestGenerateListingHash:

    def test_with_post_id(self):
        h = generate_listing_hash("some content", post_id="12345")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_without_post_id(self):
        h = generate_listing_hash("some content")
        assert isinstance(h, str)
        assert len(h) == 64

    def test_same_post_id_same_hash(self):
        h1 = generate_listing_hash("content A", post_id="abc")
        h2 = generate_listing_hash("content B", post_id="abc")
        assert h1 == h2  # post_id takes precedence

    def test_different_post_id_different_hash(self):
        h1 = generate_listing_hash("same content", post_id="aaa")
        h2 = generate_listing_hash("same content", post_id="bbb")
        assert h1 != h2

    def test_same_content_same_hash(self):
        h1 = generate_listing_hash("identical content here")
        h2 = generate_listing_hash("identical content here")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = generate_listing_hash("content one")
        h2 = generate_listing_hash("content two")
        assert h1 != h2

    def test_normalization_applied(self):
        # Same semantic content, different whitespace/case should give same hash
        h1 = generate_listing_hash("Hello  World")
        h2 = generate_listing_hash("hello world")
        assert h1 == h2
