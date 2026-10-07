from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments"
    rabbitmq_url: str = "amqp://payments:payments@localhost:5672/"
    api_key: str = "dev-api-key"

    outbox_poll_interval_seconds: float = 0.5
    outbox_batch_size: int = 50
    outbox_lock_timeout_seconds: int = 30
    outbox_max_attempts: int = 10

    gateway_min_delay_seconds: float = 2.0
    gateway_max_delay_seconds: float = 5.0
    gateway_success_rate: float = Field(default=0.9, ge=0, le=1)

    webhook_timeout_seconds: float = 5.0
    webhook_connect_timeout_seconds: float = 2.0

    @model_validator(mode="after")
    def gateway_delay_order(self) -> "Settings":
        if self.gateway_min_delay_seconds > self.gateway_max_delay_seconds:
            raise ValueError("gateway_min_delay_seconds must not exceed gateway_max_delay_seconds")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
