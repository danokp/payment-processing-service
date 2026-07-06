from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    APP_ENV: str = "local"
    API_KEY: str
    DATABASE_URL: str
    RABBITMQ_URL: str
    PAYMENT_GATEWAY_MIN_DELAY_SECONDS: int = 2
    PAYMENT_GATEWAY_MAX_DELAY_SECONDS: int = 5
    PAYMENT_GATEWAY_SUCCESS_RATE: float = 0.9
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    OUTBOX_BATCH_SIZE: int = 50
    DEFAULT_OUTBOX_MAX_ATTEMPTS: int = 3
    DEFAULT_OUTBOX_RETRY_CAP_SECONDS: int = 60
    WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    DEFAULT_PAYMENT_PROCESSING_RETRY_DELAYS_SECONDS: tuple[int, ...] = (2, 4, 8)


@lru_cache
def get_settings() -> Settings:
    return Settings()
