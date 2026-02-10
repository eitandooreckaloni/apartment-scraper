"""Integration tests for database initialisation and session management."""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.storage.models import Base, Group, Listing, NotificationLog

pytestmark = pytest.mark.integration


class TestDatabaseInit:
    """Verify that tables are created correctly from models."""

    def test_tables_created(self, db_engine):
        inspector = inspect(db_engine)
        table_names = inspector.get_table_names()
        assert "listings" in table_names
        assert "groups" in table_names
        assert "notification_log" in table_names

    def test_listing_columns(self, db_engine):
        inspector = inspect(db_engine)
        columns = {c["name"] for c in inspector.get_columns("listings")}
        expected = {
            "id", "source_group", "post_url", "post_id", "author_name",
            "raw_content", "parsed_price", "parsed_location", "parsed_rooms",
            "is_roommates", "contact_info", "images", "bonus_features",
            "parse_confidence", "parsed_by", "posted_at", "scraped_at",
            "notified", "notified_at", "matches_criteria",
        }
        assert expected.issubset(columns)


class TestSessionCRUD:
    """Basic CRUD operations via a session."""

    def test_insert_and_query_listing(self, db_session):
        listing = Listing(
            id="hash123",
            source_group="Test Group",
            post_url="https://facebook.com/p/123",
            post_id="123",
            raw_content="דירה בפלורנטין",
        )
        db_session.add(listing)
        db_session.flush()

        fetched = db_session.query(Listing).filter_by(id="hash123").first()
        assert fetched is not None
        assert fetched.raw_content == "דירה בפלורנטין"

    def test_insert_group(self, db_session):
        group = Group(
            id="g1",
            name="Tel Aviv Apartments",
            url="https://facebook.com/groups/123",
        )
        db_session.add(group)
        db_session.flush()

        fetched = db_session.query(Group).filter_by(id="g1").first()
        assert fetched is not None
        assert fetched.name == "Tel Aviv Apartments"

    def test_insert_notification_log(self, db_session):
        log = NotificationLog(
            listing_id="hash123",
            status="sent",
        )
        db_session.add(log)
        db_session.flush()

        fetched = db_session.query(NotificationLog).first()
        assert fetched is not None
        assert fetched.status == "sent"
