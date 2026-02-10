"""Dual logging system: human-friendly console + detailed debug file."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

# Project root - same as config.py
PROJECT_ROOT = Path(__file__).parent.parent

# Create logs directory in data folder
LOGS_DIR = PROJECT_ROOT / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Log file paths
DEBUG_LOG_PATH = LOGS_DIR / "debug.log"
ACTIVITY_LOG_PATH = LOGS_DIR / "activity.log"


class HumanConsoleHandler(logging.Handler):
    """
    Custom handler that prints human-friendly messages to console.
    Filters out debug-level noise and formats messages nicely.
    """
    
    # Messages to suppress (too noisy for humans)
    SUPPRESS_PATTERNS = [
        "Skipping duplicate",
        "does not match criteria",
    ]
    
    def emit(self, record):
        try:
            msg = self.format(record)
            
            # Skip suppressed patterns
            for pattern in self.SUPPRESS_PATTERNS:
                if pattern in msg:
                    return
            
            # Skip debug level for console
            if record.levelno < logging.INFO:
                return
            
            print(msg, file=sys.stdout, flush=True)
            
        except Exception:
            self.handleError(record)


class HumanFormatter(logging.Formatter):
    """Formats log messages in a human-friendly way."""
    
    # Color codes for terminal
    COLORS = {
        'INFO': '\033[92m',      # Green
        'WARNING': '\033[93m',   # Yellow  
        'ERROR': '\033[91m',     # Red
        'RESET': '\033[0m',
        'BOLD': '\033[1m',
        'DIM': '\033[2m',
    }
    
    def format(self, record):
        # Get the structlog event dict if available
        event_dict = getattr(record, '_structlog_event_dict', {})
        
        msg = record.getMessage()
        level = record.levelname
        
        # Build human-friendly message based on the log content
        human_msg = self._humanize(msg, event_dict, level)
        
        # Add timestamp for non-progress messages
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color based on level
        if level == 'ERROR':
            return f"{self.COLORS['ERROR']}[{timestamp}] Error: {human_msg}{self.COLORS['RESET']}"
        elif level == 'WARNING':
            return f"{self.COLORS['WARNING']}[{timestamp}] Warning: {human_msg}{self.COLORS['RESET']}"
        else:
            return f"{self.COLORS['DIM']}[{timestamp}]{self.COLORS['RESET']} {human_msg}"
    
    def _humanize(self, msg: str, event_dict: dict, level: str) -> str:
        """Convert structured log messages to human-friendly text."""
        
        # Startup messages
        if "Starting Apartment Scraper" in msg:
            return "Starting apartment scraper..."
        
        if "Scrape interval" in msg:
            # Extract from message like "Scrape interval: 15 minutes"
            import re
            match = re.search(r'(\d+)\s*minutes?', msg)
            minutes = match.group(1) if match else '?'
            return f"Will check for new listings every {minutes} minutes"
        
        if "Budget range" in msg:
            # Extract from message like "Budget range: 5000 - 8000 NIS"
            import re
            match = re.search(r'(\d+)\s*-\s*(\d+)', msg)
            if match:
                return f"Looking for apartments: {int(match.group(1)):,}-{int(match.group(2)):,} NIS"
            return msg
        
        if "Rooms range" in msg:
            # Extract from message like "Rooms range: 2 - 4"
            import re
            match = re.search(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)', msg)
            if match:
                return f"Rooms: {match.group(1)}-{match.group(2)}"
            return msg
        
        if "Groups to monitor" in msg:
            # Extract from message like "Groups to monitor: 5"
            import re
            match = re.search(r'(\d+)', msg)
            count = match.group(1) if match else '?'
            return f"Monitoring {count} Facebook groups"
        
        if "Database initialized" in msg:
            return "Database ready"
        
        if "Scheduler started" in msg:
            return "Scheduler started"
        
        if "Running initial scrape" in msg:
            return "\nStarting initial scan of all groups..."
        
        # Scraping messages
        if "Starting scrape job" in msg:
            return "\n--- Starting new scan ---"
        
        if "Starting Facebook scraper" in msg:
            return "Opening browser..."
        
        if "Loading existing session" in msg:
            return "Loading saved Facebook session..."
        
        if "Already logged in" in msg:
            return "Logged into Facebook"
        
        if "Not logged in" in msg:
            return "Not logged into Facebook - please authenticate first"
        
        if "Ensuring group memberships" in msg:
            return "Checking group memberships..."
        
        if "Checking group membership" in msg:
            group_name = event_dict.get('group_name', 'unknown')
            return f"  Checking: {group_name}"
        
        if "Already a member" in msg:
            group_name = event_dict.get('group_name', '')
            return f"  {group_name}: member"
        
        if "Membership pending" in msg or "pending approval" in msg:
            group_name = event_dict.get('group_name', '')
            return f"  {group_name}: pending approval"
        
        if "Group membership summary" in msg:
            members = event_dict.get('members', 0)
            pending = event_dict.get('pending', 0)
            total = event_dict.get('total_groups', 0)
            return f"Groups: {members}/{total} accessible ({pending} pending)"
        
        if "Scraping group" in msg:
            group_name = event_dict.get('group_name', 'unknown')
            return f"\nScraping: {group_name}"
        
        if "Found" in msg and "post elements" in msg:
            # Extract count from message like "Found 15 post elements"
            import re
            match = re.search(r'Found (\d+) post', msg)
            count = match.group(1) if match else '?'
            return f"  Found {count} posts"
        
        if "Extracted" in msg and "posts from" in msg:
            # Extract from "Extracted 10 posts from Group Name"
            import re
            match = re.search(r'Extracted (\d+) posts', msg)
            count = match.group(1) if match else '?'
            return f"  Extracted {count} posts"
        
        if "Scraped" in msg and "processing" in msg:
            total = event_dict.get('total', '')
            if total:
                return f"Found {total} total posts, processing..."
            # Try to extract from message
            import re
            match = re.search(r'Scraped (\d+) posts', msg)
            if match:
                return f"Found {match.group(1)} total posts, processing..."
            return "Processing posts..."
        
        if "Sending notification" in msg:
            price = event_dict.get('price', '')
            location = event_dict.get('location', '')
            if price and location:
                return f"  Found match! {location}, {price:,} NIS - sending notification"
            return "  Found matching listing - sending notification!"
        
        if "Scrape job complete" in msg:
            total = event_dict.get('total_posts', 0)
            notifications = event_dict.get('notifications_sent', 0)
            elapsed = event_dict.get('elapsed_seconds', 0)
            return f"\nScan complete: {total} posts checked, {notifications} notifications sent ({elapsed:.0f}s)"
        
        if "Scraping complete" in msg:
            total = event_dict.get('total_posts', 0)
            scraped = event_dict.get('groups_scraped', 0)
            skipped = event_dict.get('groups_skipped', 0)
            return f"Scraped {scraped} groups ({total} posts), skipped {skipped} groups"
        
        if "Facebook scraper stopped" in msg:
            return "Browser closed"
        
        if "Shutting down" in msg:
            return "Shutting down..."
        
        if "Session saved" in msg:
            return "Session saved"
        
        # Error messages - keep them informative
        if level == 'ERROR':
            error = event_dict.get('error', '')
            group_name = event_dict.get('group_name', '')
            
            if "Error scraping group" in msg:
                if "Timeout" in str(error):
                    return f"Timeout scraping {group_name} (Facebook may be slow)"
                return f"Failed to scrape {group_name}: {error}"
            
            if "Login failed" in msg or "not logged in" in msg.lower():
                return "Facebook login required - please run setup first"
            
            if "Scrape job failed" in msg:
                return f"Scan failed: {error}"
            
            return f"{msg}: {error}" if error else msg
        
        # Warning messages
        if level == 'WARNING':
            group_name = event_dict.get('group_name', '')
            
            if "Skipping group" in msg:
                status = event_dict.get('status', '')
                if "pending" in msg.lower():
                    return f"Skipping {group_name} (waiting for admin approval)"
                return f"Skipping {group_name} (not a member)"
            
            if "Failed to extract" in msg:
                return "Skipped unreadable post"
            
            return msg
        
        # Default: return original message
        return msg


def setup_logging():
    """Configure the dual logging system."""
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)
    
    # === Console Handler (Human-Friendly) ===
    console_handler = HumanConsoleHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(HumanFormatter())
    root_logger.addHandler(console_handler)
    
    # === File Handler (Detailed Debug Log) ===
    file_handler = logging.FileHandler(DEBUG_LOG_PATH, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    ))
    root_logger.addHandler(file_handler)
    
    # === Configure structlog to work with standard logging ===
    # This lets us capture the event_dict for humanizing messages
    def add_event_dict(logger, method_name, event_dict):
        """Store event dict on the record for human formatting."""
        return event_dict
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Add a processor that stores the event dict
            add_event_dict,
            # Use a custom renderer that stores event_dict on the LogRecord
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Create a custom processor formatter for structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    
    # For the file handler, use JSON-like format for debugging
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )
    
    # Update handlers with structlog formatters
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setFormatter(file_formatter)
    
    return structlog.get_logger()


def get_logger(name: Optional[str] = None):
    """Get a logger instance."""
    return structlog.get_logger(name)


# Simple human-readable print functions for key events
def print_status(message: str):
    """Print a simple status message to console."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\033[2m[{timestamp}]\033[0m {message}", flush=True)


def print_success(message: str):
    """Print a success message in green."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\033[92m[{timestamp}] {message}\033[0m", flush=True)


def print_error(message: str):
    """Print an error message in red."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\033[91m[{timestamp}] Error: {message}\033[0m", flush=True)


def print_warning(message: str):
    """Print a warning message in yellow."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\033[93m[{timestamp}] Warning: {message}\033[0m", flush=True)


def print_progress(current: int, total: int, message: str):
    """Print a progress indicator."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    bar_length = 20
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = '=' * filled + '-' * (bar_length - filled)
    print(f"\033[2m[{timestamp}]\033[0m [{bar}] {current}/{total} {message}", flush=True)
