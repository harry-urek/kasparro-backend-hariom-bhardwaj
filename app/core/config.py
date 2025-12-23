from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    COINPAPRIKA_API_KEY: str | None = None
    LOG_LEVEL: str = "INFO"
    SLACK_WEBHOOK_URL: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
