from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    CGEKO_KEY: str | None = None
    COINPAPRIKA_API_KEY: str | None = None
    LOG_LEVEL: str = "INFO"
    SLACK_WEBHOOK_URL: str | None = None
    
    # ETL Configuration
    ETL_INTERVAL_SECONDS: int = 300  # 5 minutes default
    ETL_ENABLED: bool = True  # Enable/disable automatic ETL

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore unrelated keys in local .env
    )


settings = Settings()
