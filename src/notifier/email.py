"""Email notifications via Gmail SMTP (fallback when WhatsApp limit is hit)."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import structlog

from ..config import config
from ..parser.hybrid import ParsedListing
from ..storage.models import NotificationLog, Listing
from ..storage.database import session_scope

logger = structlog.get_logger()

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class EmailNotifier:
    """Sends apartment notifications via email using Gmail SMTP."""

    def __init__(self):
        self.email_address: str = config.email_address
        self.app_password: str = config.email_app_password
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """Check if email credentials are configured."""
        if self._available is None:
            self._available = bool(self.email_address and self.app_password)
            if not self._available:
                logger.warning("Email fallback not configured (EMAIL_ADDRESS / EMAIL_APP_PASSWORD missing)")
        return self._available

    def _format_html(self, listing: Listing, parsed: ParsedListing) -> str:
        """Format a listing as an HTML email body."""
        has_bonus = parsed.has_bonus_features()

        if has_bonus:
            features_display = ", ".join(f.title() for f in parsed.bonus_features)
            header = "&#10024;&#127968; EXCITING Apartment Found! &#127968;&#10024;"
            bonus_html = f'<p><strong>Special Features:</strong> {features_display}</p>'
        else:
            header = "&#127968; New Apartment Found!"
            bonus_html = ""

        rows = ""

        if parsed.price:
            rows += f"<tr><td><strong>Price</strong></td><td>&#8362;{parsed.price:,}/month</td></tr>"
        if parsed.rooms:
            rows += f"<tr><td><strong>Rooms</strong></td><td>{parsed.rooms}</td></tr>"
        if parsed.location:
            location_display = parsed.location.replace("_", " ").title()
            if location_display.startswith("Street:"):
                location_display = location_display.replace("Street:", "")
            rows += f"<tr><td><strong>Location</strong></td><td>{location_display}</td></tr>"
        if parsed.is_roommates is not None:
            type_str = "Roommates" if parsed.is_roommates else "Whole Apartment"
            rows += f"<tr><td><strong>Type</strong></td><td>{type_str}</td></tr>"
        if parsed.contact_info:
            rows += f"<tr><td><strong>Contact</strong></td><td>{parsed.contact_info}</td></tr>"

        summary_html = f"<p>{parsed.summary}</p>" if parsed.summary else ""

        link_html = ""
        if listing.post_url:
            link_html = f'<p><a href="{listing.post_url}">View Post</a></p>'

        return f"""\
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2>{header}</h2>
    {bonus_html}
    <table cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
        {rows}
    </table>
    {summary_html}
    <p><strong>Source:</strong> {listing.source_group}</p>
    {link_html}
    <hr>
    <p style="color: #888; font-size: 12px;">
        Sent via email fallback (WhatsApp daily limit reached).
    </p>
</body>
</html>"""

    def send_notification(self, listing: Listing, parsed: ParsedListing) -> bool:
        """Send an email notification for a listing.

        Args:
            listing: Database listing record
            parsed: Parsed listing data

        Returns:
            True if sent successfully
        """
        if not self.available:
            logger.error("Email notifier not available — credentials missing")
            return False

        location_str = parsed.location.replace("_", " ").title() if parsed.location else "Unknown"
        price_str = f"{parsed.price:,} NIS" if parsed.price else "?"

        subject = f"Apartment: {location_str} — {price_str}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.email_address
        msg["To"] = self.email_address

        html_body = self._format_html(listing, parsed)
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(self.email_address, self.app_password)
                server.sendmail(self.email_address, self.email_address, msg.as_string())

            # Log successful notification
            with session_scope() as session:
                log = NotificationLog(
                    listing_id=listing.id,
                    status="sent"
                )
                session.add(log)

            logger.info(
                "Email notification sent",
                listing_id=listing.id,
                to=self.email_address,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to send email notification",
                error=str(e),
                listing_id=listing.id,
            )

            with session_scope() as session:
                log = NotificationLog(
                    listing_id=listing.id,
                    status="failed",
                    error_message=f"email: {e}"
                )
                session.add(log)

            return False
