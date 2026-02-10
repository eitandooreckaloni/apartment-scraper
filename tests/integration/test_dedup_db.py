"""Integration tests for dedup logic that requires a live database session."""

from datetime import datetime, timedelta

import pytest

from src.storage.dedup import generate_listing_hash, is_duplicate, mark_as_seen
from src.storage.models import Listing

pytestmark = pytest.mark.integration


class TestIsDuplicate:
    """Tests for is_duplicate with an in-memory SQLite session."""

    def test_no_duplicates_in_empty_db(self, db_session):
        dup, existing = is_duplicate(db_session, "brand new listing content")
        assert dup is False
        assert existing is None

    def test_exact_hash_match(self, db_session):
        content = "דירת 3 חדרים בפלורנטין 5000 שח"
        listing_hash = generate_listing_hash(content, post_id="post_001")

        # Insert a listing with the same hash
        listing = Listing(
            id=listing_hash,
            source_group="Group A",
            post_url="https://fb.com/p/1",
            post_id="post_001",
            raw_content=content,
        )
        db_session.add(listing)
        db_session.flush()

        dup, existing = is_duplicate(db_session, content, post_id="post_001")
        assert dup is True
        assert existing is not None
        assert existing.post_id == "post_001"

    def test_post_id_match(self, db_session):
        # Insert by hash of content, then look up by post_id
        listing = Listing(
            id="some_other_hash",
            source_group="Group A",
            post_url="https://fb.com/p/1",
            post_id="unique_post_id",
            raw_content="original content",
        )
        db_session.add(listing)
        db_session.flush()

        dup, existing = is_duplicate(
            db_session, "completely different content", post_id="unique_post_id"
        )
        assert dup is True

    def test_fuzzy_match(self, db_session):
        base_text = "דירת 3 חדרים בפלורנטין מחיר 5000 שקל לחודש כניסה מיידית"
        listing = Listing(
            id=generate_listing_hash(base_text),
            source_group="Group A",
            post_url="https://fb.com/p/1",
            post_id="p1",
            raw_content=base_text,
            scraped_at=datetime.utcnow(),
        )
        db_session.add(listing)
        db_session.flush()

        # Very similar text (minor wording change) should fuzzy-match
        similar = "דירת 3 חדרים בפלורנטין מחיר 5000 שקל לחודש כניסה מיידית!!!"
        dup, _ = is_duplicate(db_session, similar, similarity_threshold=85)
        assert dup is True

    def test_not_fuzzy_match_below_threshold(self, db_session):
        base_text = "דירת 3 חדרים בפלורנטין"
        listing = Listing(
            id=generate_listing_hash(base_text),
            source_group="Group A",
            post_url="https://fb.com/p/1",
            post_id="p1",
            raw_content=base_text,
            scraped_at=datetime.utcnow(),
        )
        db_session.add(listing)
        db_session.flush()

        completely_different = "סטודיו ברמת אביב 3500 שקל חדש לגמרי"
        dup, _ = is_duplicate(db_session, completely_different)
        assert dup is False


class TestMarkAsSeen:
    """Tests for mark_as_seen."""

    def test_creates_listing_record(self, db_session):
        listing = mark_as_seen(
            db_session,
            listing_id="hash_abc",
            content="some listing",
            source_group="Group B",
            post_url="https://fb.com/p/2",
            post_id="p2",
        )
        db_session.flush()

        fetched = db_session.query(Listing).filter_by(id="hash_abc").first()
        assert fetched is not None
        assert fetched.source_group == "Group B"
        assert fetched.raw_content == "some listing"

    def test_extra_kwargs_applied(self, db_session):
        listing = mark_as_seen(
            db_session,
            listing_id="hash_def",
            content="another listing",
            source_group="Group C",
            post_url="https://fb.com/p/3",
            post_id="p3",
            parsed_price=6000,
            parsed_location="florentin",
        )
        db_session.flush()

        fetched = db_session.query(Listing).filter_by(id="hash_def").first()
        assert fetched.parsed_price == 6000
        assert fetched.parsed_location == "florentin"
