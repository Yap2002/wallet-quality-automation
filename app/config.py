import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    app_env: str = os.getenv("APP_ENV", "local")
    app_name: str = os.getenv("APP_NAME", "wallet-quality-service")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://wallet:wallet@localhost:53306/wallet?charset=utf8mb4",
    )
    channel_callback_token: str = os.getenv("CHANNEL_CALLBACK_TOKEN", "local-test-channel-token")
    redis_url: str | None = os.getenv("REDIS_URL") or None


settings = Settings()
