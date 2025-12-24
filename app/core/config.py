from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    CGEKO_KEY: str | None = None
    LOG_LEVEL: str = "INFO"
    SLACK_WEBHOOK_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore unrelated keys in local .env
    )


settings = Settings()
