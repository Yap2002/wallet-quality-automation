import os
from uuid import uuid4

import pytest
from redis import Redis

from app.infrastructure.cache import TransactionStatusCache

pytestmark = pytest.mark.integration


def test_real_redis_transaction_status_round_trip() -> None:
    redis_url = os.getenv("TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_REDIS_URL is required for the optional real Redis test")
    client: Redis = Redis.from_url(redis_url)
    cache = TransactionStatusCache(client, ttl_seconds=10)
    transaction_id = uuid4()

    try:
        assert cache.record(transaction_id, "PROCESSING")
        assert cache.get(transaction_id) == "PROCESSING"
    finally:
        client.delete(f"wallet:transaction-status:{transaction_id}")
