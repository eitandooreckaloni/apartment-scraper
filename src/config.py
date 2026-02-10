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
        config_data = yaml.safe_load(f)
    return config_data


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
    
    @property
    def email_address(self) -> str:
        """Gmail address for email fallback notifications."""
        return os.getenv("EMAIL_ADDRESS", "")
    
    @property
    def email_app_password(self) -> str:
        """Gmail App Password for SMTP authentication."""
        return os.getenv("EMAIL_APP_PASSWORD", "")
    
    @property
    def apify_api_token(self) -> str:
        """Apify API token for Facebook scraping via Apify."""
        return os.getenv("APIFY_API_TOKEN", "")
    
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
    
    @property
    def bonus_features(self) -> list[str]:
        """Get bonus feature keywords to look for (e.g., roof, balcony)."""
        return self._config["criteria"].get("bonus_features", [])
    
    # Yad2 settings
    @property
    def yad2_enabled(self) -> bool:
        """Whether Yad2 scraping is enabled."""
        return self._config.get("yad2", {}).get("enabled", True)
    
    @property
    def yad2_cities(self) -> list[int]:
        """Yad2 city codes to search (5000 = Tel Aviv)."""
        return self._config.get("yad2", {}).get("cities", [5000])
    
    @property
    def yad2_property_type(self) -> str | None:
        """Property type filter for Yad2."""
        return self._config.get("yad2", {}).get("property_type")
    
    @property
    def yad2_price_min(self) -> int:
        """Min price for Yad2 (falls back to global budget)."""
        yad2_price = self._config.get("yad2", {}).get("price", {})
        return yad2_price.get("min", self.budget_min)
    
    @property
    def yad2_price_max(self) -> int:
        """Max price for Yad2 (falls back to global budget)."""
        yad2_price = self._config.get("yad2", {}).get("price", {})
        return yad2_price.get("max", self.budget_max)
    
    @property
    def yad2_rooms_min(self) -> float:
        """Min rooms for Yad2 (falls back to global rooms)."""
        yad2_rooms = self._config.get("yad2", {}).get("rooms", {})
        return yad2_rooms.get("min", self.rooms_min)
    
    @property
    def yad2_rooms_max(self) -> float:
        """Max rooms for Yad2 (falls back to global rooms)."""
        yad2_rooms = self._config.get("yad2", {}).get("rooms", {})
        return yad2_rooms.get("max", self.rooms_max)
    
    # Facebook settings
    @property
    def facebook_enabled(self) -> bool:
        """Whether Facebook scraping is enabled (disabled by default)."""
        return self._config.get("facebook", {}).get("enabled", False)
    
    @property
    def facebook_scraper_type(self) -> str:
        """Facebook scraper type: 'apify', 'library' (HTTP-based), or 'playwright' (browser automation)."""
        return self._config.get("facebook", {}).get("scraper_type", "library")
    
    @property
    def facebook_groups(self) -> list[dict[str, str]]:
        return self._config["facebook"]["groups"]
    
    @property
    def auto_join_groups(self) -> bool:
        """Whether to automatically join Facebook groups that the user isn't a member of."""
        return self._config["facebook"].get("auto_join_groups", True)
    
    @property
    def facebook_apify_actor_id(self) -> str:
        """Apify actor ID for Facebook Posts Scraper."""
        return self._config.get("facebook", {}).get("apify", {}).get("actor_id", "zanTWNqB3Poz44qdY")
    
    @property
    def facebook_apify_max_posts(self) -> int:
        """Maximum posts to fetch per group via Apify."""
        return self._config.get("facebook", {}).get("apify", {}).get("max_posts_per_group", 20)
    
    @property
    def facebook_apify_timeout(self) -> int:
        """Timeout in seconds for Apify actor run."""
        return self._config.get("facebook", {}).get("apify", {}).get("timeout_seconds", 120)
    
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
