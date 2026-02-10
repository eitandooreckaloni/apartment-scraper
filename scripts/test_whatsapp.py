#!/usr/bin/env python3
"""Quick test for WhatsApp connection."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.notifier.whatsapp import get_notifier


if __name__ == "__main__":
    print("Testing WhatsApp connection...")
    notifier = get_notifier()
    success, message = notifier.send_test_message()
    print(f"{'✓' if success else '✗'} {message}")
    sys.exit(0 if success else 1)
