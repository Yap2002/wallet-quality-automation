import pytest
from sqlalchemy.engine import make_url

from tests.framework.config import TestSettings as FrameworkSettings


def test_load_default_test_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "TEST_ENV",
        "TEST_BASE_URL",
        "TEST_DATABASE_URL",
        "TEST_REQUEST_TIMEOUT_SECONDS",
        "TEST_STARTUP_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = FrameworkSettings.from_environment()

    assert settings.environment == "test"
    assert settings.base_url is None
    assert make_url(settings.database_url).database == "wallet_test"
    assert settings.request_timeout_seconds == 5.0
    assert settings.startup_timeout_seconds == 10.0


def test_treat_empty_base_url_as_automatic_local_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_BASE_URL", "   ")

    settings = FrameworkSettings.from_environment()

    assert settings.base_url is None


def test_normalize_external_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ENV", "local")
    monkeypatch.setenv("TEST_BASE_URL", " http://127.0.0.1:8000/ ")

    settings = FrameworkSettings.from_environment()

    assert settings.environment == "local"
    assert settings.base_url == "http://127.0.0.1:8000"


@pytest.mark.parametrize(
    ("name", "value", "expected_message"),
    [
        ("TEST_ENV", "production", "TEST_ENV"),
        ("TEST_BASE_URL", "127.0.0.1:8000", "TEST_BASE_URL"),
        ("TEST_REQUEST_TIMEOUT_SECONDS", "0", "greater than zero"),
        ("TEST_STARTUP_TIMEOUT_SECONDS", "not-a-number", "must be a number"),
    ],
)
def test_reject_invalid_test_settings(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    expected_message: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=expected_message):
        FrameworkSettings.from_environment()
