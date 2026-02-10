"""Configuration management for the apartment scraper."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def load_config() -> dict[str, Any]:
    """Load configuration from config.yaml."""
    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Config:
    """Application configuration."""
    
    def __init__(self):
        self._config = load_config()
    
    # Environment variables
    @property
    def fb_email(self) -> str:
        return os.getenv("FB_EMAIL", "")
    
    @property
    def fb_password(self) -> str:
        return os.getenv("FB_PASSWORD", "")
    
    @property
    def openai_api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")
    
    @property
    def twilio_account_sid(self) -> str:
        return os.getenv("TWILIO_ACCOUNT_SID", "")
    
    @property
    def twilio_auth_token(self) -> str:
        return os.getenv("TWILIO_AUTH_TOKEN", "")
    
    @property
    def twilio_whatsapp_from(self) -> str:
        return os.getenv("TWILIO_WHATSAPP_FROM", "")
    
    @property
    def twilio_whatsapp_to(self) -> str:
        return os.getenv("TWILIO_WHATSAPP_TO", "")
    
    @property
    def database_path(self) -> Path:
        db_path = os.getenv("DATABASE_PATH", "data/apartments.db")
        return PROJECT_ROOT / db_path
    
    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")
    
    # Scraper settings
    @property
    def scraper_interval_minutes(self) -> int:
        return self._config["scraper"]["interval_minutes"]
    
    @property
    def scraper_min_delay(self) -> int:
        return self._config["scraper"]["min_delay"]
    
    @property
    def scraper_max_delay(self) -> int:
        return self._config["scraper"]["max_delay"]
    
    @property
    def posts_per_group(self) -> int:
        return self._config["scraper"]["posts_per_group"]
    
    @property
    def session_path(self) -> Path:
        return PROJECT_ROOT / self._config["scraper"]["session_path"]
    
    # Criteria settings
    @property
    def budget_min(self) -> int:
        return self._config["criteria"]["budget"]["min"]
    
    @property
    def budget_max(self) -> int:
        return self._config["criteria"]["budget"]["max"]
    
    @property
    def locations(self) -> list[str]:
        return self._config["criteria"]["locations"]
    
    @property
    def rooms_min(self) -> float:
        return self._config["criteria"]["rooms"]["min"]
    
    @property
    def rooms_max(self) -> float:
        return self._config["criteria"]["rooms"]["max"]
    
    @property
    def listing_type(self) -> str:
        return self._config["criteria"]["listing_type"]
    
    # Facebook groups
    @property
    def facebook_groups(self) -> list[dict[str, str]]:
        return self._config["facebook"]["groups"]
    
    # Parsing settings
    @property
    def use_ai_fallback(self) -> bool:
        return self._config["parsing"]["use_ai_fallback"]
    
    @property
    def regex_confidence_threshold(self) -> float:
        return self._config["parsing"]["regex_confidence_threshold"]
    
    @property
    def ai_model(self) -> str:
        return self._config["parsing"]["ai_model"]
    
    # Notification settings
    @property
    def include_images(self) -> bool:
        return self._config["notifications"]["include_images"]
    
    @property
    def max_notifications_per_hour(self) -> int:
        return self._config["notifications"]["max_per_hour"]


# Global config instance
config = Config()
