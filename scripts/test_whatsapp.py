#!/usr/bin/env python3
"""Quick test for WhatsApp connection."""

import sys
import os
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# #region agent log
LOG_PATH = PROJECT_ROOT / ".cursor" / "debug.log"
def _dbg(msg, data, hyp):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"location": "test_whatsapp.py", "message": msg, "data": data, "hypothesisId": hyp, "timestamp": __import__("time").time()}) + "\n")
# #endregion

# #region agent log - H1: Check if .env file exists and dotenv loads it
env_path = PROJECT_ROOT / ".env"
_dbg("H1: .env file check", {"exists": env_path.exists(), "path": str(env_path)}, "H1")
# #endregion

from dotenv import load_dotenv
load_result = load_dotenv(env_path)

# #region agent log - H1: dotenv load result
_dbg("H1: load_dotenv result", {"loaded": load_result}, "H1")
# #endregion

# #region agent log - H2/H3: Check env var values (masked)
sid = os.getenv("TWILIO_ACCOUNT_SID", "")
token = os.getenv("TWILIO_AUTH_TOKEN", "")
from_num = os.getenv("TWILIO_WHATSAPP_FROM", "")
to_num = os.getenv("TWILIO_WHATSAPP_TO", "")
_dbg("H2/H3: Env vars check", {
    "sid_len": len(sid), "sid_prefix": sid[:4] if sid else "", "sid_has_whitespace": sid != sid.strip(),
    "token_len": len(token), "token_prefix": token[:4] if token else "", "token_has_whitespace": token != token.strip(),
    "from_len": len(from_num), "from_value": from_num,
    "to_len": len(to_num), "to_value": to_num,
}, "H2")
# #endregion

from src.notifier.whatsapp import get_notifier
from src.config import config


if __name__ == "__main__":
    print("Testing WhatsApp connection...")
    
    # #region agent log - H6: Check what config module actually has
    _dbg("H6: Config module values", {
        "config_sid_len": len(config.twilio_account_sid),
        "config_sid_prefix": config.twilio_account_sid[:4] if config.twilio_account_sid else "",
        "config_token_len": len(config.twilio_auth_token),
        "config_token_prefix": config.twilio_auth_token[:4] if config.twilio_auth_token else "",
        "config_from": config.twilio_whatsapp_from,
        "config_to": config.twilio_whatsapp_to,
    }, "H6")
    # #endregion
    
    notifier = get_notifier()
    
    # #region agent log - H4: Check what notifier has
    _dbg("H4: Notifier client check", {"client_exists": notifier.client is not None}, "H4")
    # #endregion
    
    # #region agent log - H7: Test raw Twilio auth with account fetch
    try:
        from twilio.rest import Client
        test_client = Client(config.twilio_account_sid, config.twilio_auth_token)
        account = test_client.api.accounts(config.twilio_account_sid).fetch()
        _dbg("H7: Raw Twilio auth test", {"success": True, "account_status": account.status, "friendly_name": account.friendly_name}, "H7")
    except Exception as e:
        _dbg("H7: Raw Twilio auth test", {"success": False, "error": str(e)[:200]}, "H7")
    # #endregion
    
    success, message = notifier.send_test_message()
    
    # #region agent log - Result
    _dbg("Result", {"success": success, "message": message[:100] if message else ""}, "result")
    # #endregion
    
    print(f"{'✓' if success else '✗'} {message}")
    sys.exit(0 if success else 1)
