from typing import get_args

from fastapi.params import Depends

from app.api.dependencies import DatabaseSession


def test_database_transaction_finishes_before_response_is_sent() -> None:
    metadata = get_args(DatabaseSession)[1:]
    database_dependency = next(item for item in metadata if isinstance(item, Depends))

    assert database_dependency.scope == "function", (
        "database dependency must use function scope so commit completes before "
        "the HTTP response is sent"
    )
