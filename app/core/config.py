from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = "local"
    api_key: str = Field(alias="API_KEY")
    database_url: str = Field(alias="DATABASE_URL")
    rabbitmq_url: str = Field(alias="RABBITMQ_URL")
    payment_gateway_min_delay_seconds: int = 2
    payment_gateway_max_delay_seconds: int = 5
    payment_gateway_success_rate: float = 0.9
    outbox_poll_interval_seconds: float = 1.0
    outbox_batch_size: int = 50
    webhook_timeout_seconds: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
