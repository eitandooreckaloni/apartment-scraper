"""SQLAlchemy models for apartment listings."""

from datetime import datetime
from typing import Optional
import json

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Listing(Base):
    """Represents an apartment listing from Facebook."""
    
    __tablename__ = "listings"
    
    # Primary key - hash of content for deduplication
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # Source information
    source_group: Mapped[str] = mapped_column(String(255))
    post_url: Mapped[str] = mapped_column(String(512))
    post_id: Mapped[str] = mapped_column(String(64), index=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Raw content
    raw_content: Mapped[str] = mapped_column(Text)
    
    # Parsed fields
    parsed_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    parsed_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    parsed_rooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_roommates: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    contact_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Images stored as JSON array
    _images: Mapped[Optional[str]] = mapped_column("images", Text, nullable=True)
    
    # Parsing metadata
    parse_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    parsed_by: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'regex' or 'ai'
    
    # Timestamps and status
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Filtering result
    matches_criteria: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    @property
    def images(self) -> list[str]:
        """Get images as a list."""
        if self._images:
            return json.loads(self._images)
        return []
    
    @images.setter
    def images(self, value: list[str]):
        """Set images from a list."""
        self._images = json.dumps(value) if value else None
    
    def __repr__(self) -> str:
        return f"<Listing {self.id[:8]}... price={self.parsed_price} location={self.parsed_location}>"


class Group(Base):
    """Represents a Facebook group to monitor."""
    
    __tablename__ = "groups"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(512))
    
    # Tracking
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_post_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Stats
    total_posts_scraped: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self) -> str:
        return f"<Group {self.name}>"


class NotificationLog(Base):
    """Log of sent notifications for rate limiting."""
    
    __tablename__ = "notification_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[str] = mapped_column(String(64), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20))  # 'sent', 'failed'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
