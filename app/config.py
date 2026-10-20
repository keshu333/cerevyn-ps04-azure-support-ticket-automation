"""Application configuration module.

Loads environment variables with robust defaults for local development and
cloud deployment (e.g., Azure App Service).
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent


def get_env_bool(key: str, default: bool = False) -> bool:
    """Parse boolean environment variables."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "t", "yes", "y")


class Settings:
    """Central application settings."""

    # Server settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    APP_NAME: str = "Cerevyn Azure Support Ticket Automation"
    APP_VERSION: str = "1.0.0"

    # Database settings
    # Default to data/tickets.db inside project root
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        str(BASE_DIR / "data" / "tickets.db")
    )

    # Validation bounds
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", "2000"))
    MIN_MESSAGE_LENGTH: int = int(os.getenv("MIN_MESSAGE_LENGTH", "5"))

    # Classifier settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.60"))


settings = Settings()
