"""Short-lived quote cache. Redis is not the system of record for prices."""

import json
import logging
import time
from abc import ABC, abstractmethod
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.schemas.market_data import QuoteResponse

logger = logging.getLogger(__name__)

_cache: "QuoteCache | None" = None


class QuoteCache(ABC):
    @abstractmethod
    def get(self, stock_id: UUID) -> QuoteResponse | None:
        """Return a fresh quote, or None when the entry is missing or expired."""

    @abstractmethod
    def put(self, quote: QuoteResponse, ttl_seconds: int) -> None:
        """Store a quote until the TTL elapses."""


class MemoryQuoteCache(QuoteCache):
    """Process-local cache used when Redis is down and in tests."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[float, str]] = {}

    def get(self, stock_id: UUID) -> QuoteResponse | None:
        key = _key(stock_id)
        found = self._values.get(key)
        if found is None:
            return None
        expires_at, payload = found
        if expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return _decode(payload)

    def put(self, quote: QuoteResponse, ttl_seconds: int) -> None:
        self._values[_key(quote.stock_id)] = (time.monotonic() + ttl_seconds, _encode(quote))


class RedisQuoteCache(QuoteCache):
    def __init__(self, client: Redis) -> None:
        self._client = client

    def get(self, stock_id: UUID) -> QuoteResponse | None:
        try:
            payload = self._client.get(_key(stock_id))
        except RedisError:
            logger.warning("quote cache read failed")
            return None
        if payload is None:
            return None
        return _decode(payload)

    def put(self, quote: QuoteResponse, ttl_seconds: int) -> None:
        try:
            self._client.setex(_key(quote.stock_id), ttl_seconds, _encode(quote))
        except RedisError:
            logger.warning("quote cache write failed")


def get_quote_cache() -> QuoteCache:
    """Reuse one cache for the process. Redis is preferred when it answers."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        client = get_redis()
        client.ping()
        _cache = RedisQuoteCache(client)
    except RedisError:
        logger.warning("Redis is unavailable; quotes are cached in-process until restart")
        _cache = MemoryQuoteCache()
    return _cache


def _key(stock_id: UUID) -> str:
    return f"market:quote:{stock_id}"


def _encode(quote: QuoteResponse) -> str:
    return json.dumps(quote.model_dump(mode="json"))


def _decode(payload: str) -> QuoteResponse | None:
    try:
        return QuoteResponse.model_validate_json(payload)
    except (ValueError, TypeError):
        logger.warning("quote cache entry is invalid")
        return None
