from typing import Any
from unittest.mock import Mock
from uuid import uuid4

from redis.exceptions import ConnectionError

from app.infrastructure.cache import TransactionStatusCache


def test_transaction_status_cache_round_trip() -> None:
    client: Any = Mock()
    client.get.return_value = b"SUCCEEDED"
    cache = TransactionStatusCache(client, ttl_seconds=30)
    transaction_id = uuid4()

    assert cache.record(transaction_id, "SUCCEEDED")
    assert cache.get(transaction_id) == "SUCCEEDED"
    client.setex.assert_called_once_with(
        f"wallet:transaction-status:{transaction_id}", 30, "SUCCEEDED"
    )


def test_redis_outage_does_not_break_mysql_flow() -> None:
    client: Any = Mock()
    client.setex.side_effect = ConnectionError("Redis is unavailable")
    client.get.side_effect = ConnectionError("Redis is unavailable")
    cache = TransactionStatusCache(client)

    assert not cache.record(uuid4(), "PROCESSING")
    assert cache.get(uuid4()) is None
