"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database URLs
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/masjid_db"
    SYNC_DATABASE_URL: str = "postgresql://user:password@localhost:5432/masjid_db"
    
    # Application settings
    DEBUG: bool = False
    
    # Scraping settings
    SCRAPE_INTERVAL_HOURS: int = 6
    REQUEST_DELAY_SECONDS: float = 1.5
    BASE_URL: str = "https://masjidboardlive.com"

    class Config:
        env_file = ".env"


settings = Settings()
