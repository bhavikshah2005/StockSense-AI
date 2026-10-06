"""Short-lived technical-analysis cache. PostgreSQL keeps the persisted rows."""

import json
import logging
import time

from redis import Redis
from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.schemas.technical import TechnicalAnalysisResponse

logger = logging.getLogger(__name__)

_cache: "TechnicalCache | None" = None


class TechnicalCache:
    def get(self, key: str) -> TechnicalAnalysisResponse | None:
        raise NotImplementedError

    def put(self, key: str, payload: TechnicalAnalysisResponse, ttl_seconds: int) -> None:
        raise NotImplementedError


class MemoryTechnicalCache(TechnicalCache):
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> TechnicalAnalysisResponse | None:
        found = self._values.get(key)
        if found is None:
            return None
        expires_at, payload = found
        if expires_at <= time.monotonic():
            self._values.pop(key, None)
            return None
        return _decode(payload)

    def put(self, key: str, payload: TechnicalAnalysisResponse, ttl_seconds: int) -> None:
        self._values[key] = (time.monotonic() + ttl_seconds, payload.model_dump_json())


class RedisTechnicalCache(TechnicalCache):
    def __init__(self, client: Redis) -> None:
        self._client = client

    def get(self, key: str) -> TechnicalAnalysisResponse | None:
        try:
            payload = self._client.get(key)
        except RedisError:
            logger.warning("technical cache read failed")
            return None
        if payload is None:
            return None
        return _decode(payload)

    def put(self, key: str, payload: TechnicalAnalysisResponse, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, payload.model_dump_json())
        except RedisError:
            logger.warning("technical cache write failed")


def get_technical_cache() -> TechnicalCache:
    global _cache
    if _cache is not None:
        return _cache
    try:
        client = get_redis()
        client.ping()
        _cache = RedisTechnicalCache(client)
    except RedisError:
        logger.warning("Redis is unavailable; technical analysis is cached in-process until restart")
        _cache = MemoryTechnicalCache()
    return _cache


def technical_cache_key(stock_id: object, interval: str, start: object, end: object, price_as_of: object) -> str:
    return f"technical:{stock_id}:{interval}:{start}:{end}:patterns-1:indicators-1:{price_as_of}"


def _decode(payload: str | bytes) -> TechnicalAnalysisResponse | None:
    try:
        if isinstance(payload, bytes):
            payload = payload.decode()
        return TechnicalAnalysisResponse.model_validate(json.loads(payload))
    except (ValueError, TypeError):
        logger.warning("technical cache entry is invalid")
        return None
