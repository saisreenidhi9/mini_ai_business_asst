"""
Application configuration module.
Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings with defaults."""

    def __init__(self):
        self.BASE_DIR: Path = BASE_DIR
        self.DATABASE_PATH: Path = self.BASE_DIR / os.getenv("DATABASE_PATH", "database/sales_bi.db")
        self.DATA_DIR: Path = self.BASE_DIR / os.getenv("DATA_DIR", "data")
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "8000"))
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def has_llm_configured(self) -> bool:
        """Check whether genuine LLM API credentials are configured."""
        return bool(self.GEMINI_API_KEY or self.OPENAI_API_KEY)


settings = Settings()
