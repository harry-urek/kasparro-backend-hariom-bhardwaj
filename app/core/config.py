from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Environment mode: dev or prod
    ENV: Literal["dev", "prod"] = "dev"

    # Database
    DATABASE_URL: str

    # API Keys
    CGEKO_KEY: str | None = None
    COINPAPRIKA_API_KEY: str | None = None

    # Logging
    LOG_LEVEL: str = "INFO"
    SLACK_WEBHOOK_URL: str | None = None

    # ETL Configuration
    ETL_INTERVAL_SECONDS: int = 300  # 5 minutes default
    ETL_ENABLED: bool = True  # Enable/disable automatic ETL

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore unrelated keys in local .env
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENV == "prod"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENV == "dev"

    @property
    def debug_enabled(self) -> bool:
        """Debug mode is only enabled in development."""
        return self.is_development

    @property
    def effective_log_level(self) -> str:
        """Return appropriate log level based on environment."""
        if self.is_production:
            # In production, minimum INFO level (ignore DEBUG)
            return self.LOG_LEVEL if self.LOG_LEVEL.upper() != "DEBUG" else "INFO"
        return self.LOG_LEVEL

    @property
    def docs_enabled(self) -> bool:
        """Swagger/ReDoc docs enabled based on environment."""
        # Docs available in dev, disabled in prod for security
        return self.is_development


settings = Settings()
