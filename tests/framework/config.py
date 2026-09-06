import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TestSettings:
    """Test runtime values loaded from environment variables."""

    environment: str
    base_url: str | None
    database_url: str
    request_timeout_seconds: float
    startup_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "TestSettings":
        environment = os.getenv("TEST_ENV", "test").strip().lower()
        if environment not in {"local", "test"}:
            raise ValueError("TEST_ENV must be 'local' or 'test'")

        raw_base_url = os.getenv("TEST_BASE_URL", "").strip()
        base_url = raw_base_url.rstrip("/") or None
        if base_url is not None and not base_url.startswith(("http://", "https://")):
            raise ValueError("TEST_BASE_URL must start with http:// or https://")

        return cls(
            environment=environment,
            base_url=base_url,
            database_url=os.getenv(
                "TEST_DATABASE_URL",
                "mysql+pymysql://wallet:wallet@localhost:53306/wallet_test?charset=utf8mb4",
            ),
            request_timeout_seconds=_positive_float(
                "TEST_REQUEST_TIMEOUT_SECONDS",
                default=5.0,
            ),
            startup_timeout_seconds=_positive_float(
                "TEST_STARTUP_TIMEOUT_SECONDS",
                default=10.0,
            ),
        )


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value
