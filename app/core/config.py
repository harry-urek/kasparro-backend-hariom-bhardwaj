"""Configuration management"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # App
    app_name: str = "Kasparro Backend"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./app.db"

    # API Keys and Secrets
    api_key: Optional[str] = None
    secret_key: str = "change-me-in-production"

    # External APIs
    external_api_url: Optional[str] = None
    external_api_key: Optional[str] = None

    # CSV Source
    csv_file_path: Optional[str] = None

    # ETL
    etl_batch_size: int = 100
    etl_schedule: str = "0 */6 * * *"  # Every 6 hours

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
