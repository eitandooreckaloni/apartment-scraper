"""Shared fixtures for apartment-scraper tests."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.storage.models import Base


# ---------------------------------------------------------------------------
# Mock config fixture
# ---------------------------------------------------------------------------

def _make_mock_config():
    """Build a MagicMock that behaves like src.config.Config."""
    cfg = MagicMock()

    # Criteria
    cfg.budget_min = 4000
    cfg.budget_max = 8000
    cfg.locations = [
        "florentin",
        "פלורנטין",
        "rothschild",
        "רוטשילד",
        "neve_tzedek",
        "lev_hair",
    ]
    cfg.rooms_min = 2
    cfg.rooms_max = 4
    cfg.listing_type = "whole_apartment"
    cfg.bonus_features = [
        "roof",
        "גג",
        "rooftop",
        "balcony",
        "מרפסת",
        "big windows",
        "חלונות גדולים",
        "windows",
        "חלונות",
        "penthouse",
        "פנטהאוז",
    ]

    # Parsing
    cfg.use_ai_fallback = False
    cfg.regex_confidence_threshold = 0.6
    cfg.ai_model = "gpt-4o-mini"
    cfg.openai_api_key = ""

    # Scraper
    cfg.scraper_interval_minutes = 3
    cfg.posts_per_group = 20

    # Notifications
    cfg.include_images = True
    cfg.max_notifications_per_hour = 20

    return cfg


@pytest.fixture()
def mock_config():
    """Patch src.config.config globally and return the mock object."""
    cfg = _make_mock_config()
    with patch("src.config.config", cfg):
        # Also patch the config references inside individual modules so that
        # code which imported `config` at module level sees the mock.
        with patch("src.parser.regex_parser.config", cfg), \
             patch("src.filters.criteria.config", cfg):
            yield cfg


# ---------------------------------------------------------------------------
# In-memory database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_engine():
    """Create an in-memory SQLite engine with tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Yield a transactional DB session that rolls back after the test."""
    SessionLocal = sessionmaker(bind=db_engine)
    session: Session = SessionLocal()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Sample listing texts
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_hebrew_listing():
    """Realistic Hebrew apartment listing from a Facebook group."""
    return (
        "להשכרה דירת 3 חדרים בפלורנטין\n"
        "רחוב ויטל 15\n"
        "קומה 3, מרפסת שמש, משופצת\n"
        "מחיר: 6,500 ש\"ח לחודש\n"
        "כניסה מיידית\n"
        "טלפון: 052-123-4567"
    )


@pytest.fixture()
def sample_english_listing():
    """Realistic English apartment listing."""
    return (
        "Beautiful 2.5 room apartment for rent in Neve Tzedek\n"
        "Fully renovated, bright, big windows, rooftop access\n"
        "₪5,500 per month\n"
        "Available from March 1st\n"
        "Contact: 0501234567"
    )


@pytest.fixture()
def sample_roommate_listing():
    """Hebrew roommate listing."""
    return (
        "מחפשים שותף/ה לדירה ברוטשילד!\n"
        "חדר בדירת 3 חדרים\n"
        "2,800 ש\"ח כולל ארנונה\n"
        "050-9876543"
    )
