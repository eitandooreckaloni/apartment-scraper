"""WhatsApp notifications via Twilio."""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from ..config import config
from ..parser.hybrid import ParsedListing
from ..storage.models import NotificationLog, Listing
from ..storage.database import session_scope

logger = structlog.get_logger()


class WhatsAppNotifier:
    """Sends apartment notifications via WhatsApp using Twilio."""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Twilio client."""
        if config.twilio_account_sid and config.twilio_auth_token:
            self.client = Client(config.twilio_account_sid, config.twilio_auth_token)
            logger.info("Twilio client initialized")
        else:
            logger.warning("Twilio credentials not configured")
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        with session_scope() as session:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_count = session.query(NotificationLog).filter(
                NotificationLog.sent_at >= hour_ago,
                NotificationLog.status == "sent"
            ).count()
            
            if recent_count >= config.max_notifications_per_hour:
                logger.warning(
                    "Rate limit reached",
                    sent_this_hour=recent_count,
                    limit=config.max_notifications_per_hour
                )
                return False
            
            return True
    
    def _format_message(self, listing: Listing, parsed: ParsedListing) -> str:
        """Format a WhatsApp message for a listing."""
        lines = ["🏠 *New Apartment Found!*", ""]
        
        # Price
        if parsed.price:
            lines.append(f"💰 *Price:* ₪{parsed.price:,}/month")
        
        # Rooms
        if parsed.rooms:
            lines.append(f"🚪 *Rooms:* {parsed.rooms}")
        
        # Location
        if parsed.location:
            location_display = parsed.location.replace("_", " ").title()
            if location_display.startswith("Street:"):
                location_display = location_display.replace("Street:", "📍 ")
            lines.append(f"📍 *Location:* {location_display}")
        
        # Type
        if parsed.is_roommates is not None:
            type_str = "Roommates" if parsed.is_roommates else "Whole Apartment"
            lines.append(f"🏷️ *Type:* {type_str}")
        
        # Contact
        if parsed.contact_info:
            lines.append(f"📞 *Contact:* {parsed.contact_info}")
        
        # Summary from AI
        if parsed.summary:
            lines.append("")
            lines.append(f"📝 {parsed.summary}")
        
        # Source
        lines.append("")
        lines.append(f"📌 *Source:* {listing.source_group}")
        
        # Link
        if listing.post_url:
            lines.append("")
            lines.append(f"🔗 {listing.post_url}")
        
        return "\n".join(lines)
    
    def send_notification(self, listing: Listing, parsed: ParsedListing) -> bool:
        """Send a WhatsApp notification for a listing.
        
        Args:
            listing: Database listing record
            parsed: Parsed listing data
        
        Returns:
            True if sent successfully
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return False
        
        if not self._check_rate_limit():
            return False
        
        message_body = self._format_message(listing, parsed)
        
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=config.twilio_whatsapp_from,
                to=config.twilio_whatsapp_to
            )
            
            # Log successful notification
            with session_scope() as session:
                log = NotificationLog(
                    listing_id=listing.id,
                    status="sent"
                )
                session.add(log)
            
            logger.info(
                "WhatsApp notification sent",
                message_sid=message.sid,
                listing_id=listing.id
            )
            
            return True
            
        except TwilioRestException as e:
            logger.error(
                "Failed to send WhatsApp notification",
                error=str(e),
                listing_id=listing.id
            )
            
            # Log failed notification
            with session_scope() as session:
                log = NotificationLog(
                    listing_id=listing.id,
                    status="failed",
                    error_message=str(e)
                )
                session.add(log)
            
            return False


# Global notifier instance
_notifier: Optional[WhatsAppNotifier] = None


def get_notifier() -> WhatsAppNotifier:
    """Get or create the WhatsApp notifier."""
    global _notifier
    if _notifier is None:
        _notifier = WhatsAppNotifier()
    return _notifier


def send_listing_notification(listing: Listing, parsed: ParsedListing) -> bool:
    """Convenience function to send a notification."""
    return get_notifier().send_notification(listing, parsed)
