"""Short-lived cache for one history query. PostgreSQL keeps the bars."""

import json
import logging
import time

from redis import Redis
from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.schemas.market_data import HistoryResponse

logger = logging.getLogger(__name__)

_cache: "HistoryCache | None" = None


class HistoryCache:
    def get(self, key: str) -> HistoryResponse | None:
        raise NotImplementedError

    def put(self, key: str, payload: HistoryResponse, ttl_seconds: int) -> None:
        raise NotImplementedError


class MemoryHistoryCache(HistoryCache):
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> HistoryResponse | None:
        found = self._values.get(key)
        if found is None:
            return None
        expires_at, payload = found
        if expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return _decode(payload)

    def put(self, key: str, payload: HistoryResponse, ttl_seconds: int) -> None:
        self._values[key] = (time.monotonic() + ttl_seconds, _encode(payload))


class RedisHistoryCache(HistoryCache):
    def __init__(self, client: Redis) -> None:
        self._client = client

    def get(self, key: str) -> HistoryResponse | None:
        try:
            payload = self._client.get(key)
        except RedisError:
            logger.warning("history cache read failed")
            return None
        if payload is None:
            return None
        return _decode(payload)

    def put(self, key: str, payload: HistoryResponse, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, _encode(payload))
        except RedisError:
            logger.warning("history cache write failed")


def get_history_cache() -> HistoryCache:
    global _cache
    if _cache is not None:
        return _cache
    try:
        client = get_redis()
        client.ping()
        _cache = RedisHistoryCache(client)
    except RedisError:
        logger.warning("Redis is unavailable; history responses are cached in-process until restart")
        _cache = MemoryHistoryCache()
    return _cache


def history_cache_key(stock_id: object, interval: str, start: object, end: object) -> str:
    return f"market:history:{stock_id}:{interval}:{start}:{end}"


def _encode(payload: HistoryResponse) -> str:
    return json.dumps(payload.model_dump(mode="json"))


def _decode(payload: str) -> HistoryResponse | None:
    try:
        return HistoryResponse.model_validate_json(payload)
    except (ValueError, TypeError):
        logger.warning("history cache entry is invalid")
        return None
