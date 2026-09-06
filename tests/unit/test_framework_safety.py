from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from tests.framework.clients.wallet_api_client import redact_sensitive_data
from tests.framework.database import DatabaseClient
from tests.framework.models import UserData


def test_redact_credentials_before_attaching_report_data() -> None:
    original = {
        "id": "user-id",
        "api_key": "plaintext-key",
        "nested": {
            "Authorization": "Bearer plaintext-key",
            "value": "safe-value",
        },
    }

    redacted = redact_sensitive_data(original)

    assert redacted == {
        "id": "user-id",
        "api_key": "***REDACTED***",
        "nested": {
            "Authorization": "***REDACTED***",
            "value": "safe-value",
        },
    }


def test_database_cleanup_client_rejects_non_test_database() -> None:
    engine = create_engine("mysql+pymysql://wallet:wallet@localhost:53306/wallet?charset=utf8mb4")
    try:
        with pytest.raises(ValueError, match="ending in '_test'"):
            DatabaseClient(engine)
    finally:
        engine.dispose()


def test_user_data_repr_does_not_expose_api_key() -> None:
    user = UserData(
        id=uuid4(),
        email="safe@example.com",
        status="ACTIVE",
        api_key="must-not-appear",
    )

    assert "must-not-appear" not in repr(user)
    assert "api_key" not in repr(user)
