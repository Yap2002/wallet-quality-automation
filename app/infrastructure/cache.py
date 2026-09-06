import logging
from functools import lru_cache
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger("wallet.cache")


class TransactionStatusCache:
    """Optional Redis acceleration; MySQL remains the source of truth."""

    def __init__(self, client: Redis, ttl_seconds: int = 60) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    def record(self, transaction_id: UUID, status: str) -> bool:
        try:
            self._client.setex(
                f"wallet:transaction-status:{transaction_id}",
                self._ttl_seconds,
                status,
            )
            return True
        except RedisError:
            logger.warning(
                "Redis status cache unavailable; continuing with MySQL",
                extra={"event": "redis_cache_fallback", "transaction_id": transaction_id},
            )
            return False

    def get(self, transaction_id: UUID) -> str | None:
        try:
            value = self._client.get(f"wallet:transaction-status:{transaction_id}")
        except RedisError:
            return None
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else str(value)


@lru_cache(maxsize=1)
def get_transaction_status_cache() -> TransactionStatusCache | None:
    if settings.redis_url is None:
        return None
    client: Redis = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
        decode_responses=False,
    )
    return TransactionStatusCache(client)


def record_transaction_status(transaction_id: UUID, status: str) -> bool:
    cache = get_transaction_status_cache()
    return False if cache is None else cache.record(transaction_id, status)
