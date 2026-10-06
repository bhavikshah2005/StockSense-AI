"""Short-lived fundamental and valuation response cache. PostgreSQL remains the store."""

import logging
import time
from abc import ABC, abstractmethod
from uuid import UUID

from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.schemas.fundamentals import (
    FundamentalHistoryResponse,
    FundamentalReportResponse,
    ValuationHistoryResponse,
    ValuationResponse,
)

logger = logging.getLogger(__name__)

_cache: "FundamentalCache | None" = None


class FundamentalCache(ABC):
    @abstractmethod
    def get_report(self, key: str) -> FundamentalReportResponse | None:
        """Return a cached report response, or None when missing or expired."""

    @abstractmethod
    def put_report(self, key: str, value: FundamentalReportResponse, ttl_seconds: int) -> None:
        """Store a report response until the TTL elapses."""

    @abstractmethod
    def get_history(self, key: str) -> FundamentalHistoryResponse | None:
        """Return a cached fundamental history response."""

    @abstractmethod
    def put_history(self, key: str, value: FundamentalHistoryResponse, ttl_seconds: int) -> None:
        """Store a fundamental history response."""

    @abstractmethod
    def get_valuation(self, key: str) -> ValuationResponse | None:
        """Return a cached valuation response."""

    @abstractmethod
    def put_valuation(self, key: str, value: ValuationResponse, ttl_seconds: int) -> None:
        """Store a valuation response."""

    @abstractmethod
    def get_valuation_history(self, key: str) -> ValuationHistoryResponse | None:
        """Return a cached valuation history response."""

    @abstractmethod
    def put_valuation_history(self, key: str, value: ValuationHistoryResponse, ttl_seconds: int) -> None:
        """Store a valuation history response."""

    @abstractmethod
    def invalidate_stock(self, stock_id: UUID) -> None:
        """Drop cached fundamental and valuation responses for one listing."""


class MemoryFundamentalCache(FundamentalCache):
    """Process-local cache used when Redis is down and in tests."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[float, str, type[BaseModel]]] = {}

    def get_report(self, key: str) -> FundamentalReportResponse | None:
        return self._read(key, FundamentalReportResponse)

    def put_report(self, key: str, value: FundamentalReportResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def get_history(self, key: str) -> FundamentalHistoryResponse | None:
        return self._read(key, FundamentalHistoryResponse)

    def put_history(self, key: str, value: FundamentalHistoryResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def get_valuation(self, key: str) -> ValuationResponse | None:
        return self._read(key, ValuationResponse)

    def put_valuation(self, key: str, value: ValuationResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def get_valuation_history(self, key: str) -> ValuationHistoryResponse | None:
        return self._read(key, ValuationHistoryResponse)

    def put_valuation_history(self, key: str, value: ValuationHistoryResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def invalidate_stock(self, stock_id: UUID) -> None:
        prefixes = (f"fundamentals:{stock_id}:", f"valuation:{stock_id}:")
        for key in [item for item in self._values if item.startswith(prefixes)]:
            self._values.pop(key, None)

    def _read(self, key: str, model: type[BaseModel]) -> BaseModel | None:
        found = self._values.get(key)
        if found is None:
            return None
        expires_at, payload, stored = found
        if expires_at <= time.monotonic() or stored is not model:
            self._values.pop(key, None)
            return None
        try:
            return model.model_validate_json(payload)
        except ValueError:
            self._values.pop(key, None)
            return None

    def _write(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        self._values[key] = (time.monotonic() + ttl_seconds, value.model_dump_json(), type(value))


class RedisFundamentalCache(FundamentalCache):
    def __init__(self, client: Redis) -> None:
        self._client = client

    def get_report(self, key: str) -> FundamentalReportResponse | None:
        return self._read(key, FundamentalReportResponse)

    def put_report(self, key: str, value: FundamentalReportResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def get_history(self, key: str) -> FundamentalHistoryResponse | None:
        return self._read(key, FundamentalHistoryResponse)

    def put_history(self, key: str, value: FundamentalHistoryResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def get_valuation(self, key: str) -> ValuationResponse | None:
        return self._read(key, ValuationResponse)

    def put_valuation(self, key: str, value: ValuationResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def get_valuation_history(self, key: str) -> ValuationHistoryResponse | None:
        return self._read(key, ValuationHistoryResponse)

    def put_valuation_history(self, key: str, value: ValuationHistoryResponse, ttl_seconds: int) -> None:
        self._write(key, value, ttl_seconds)

    def invalidate_stock(self, stock_id: UUID) -> None:
        try:
            keys: list[str] = []
            for prefix in (f"fundamentals:{stock_id}:", f"valuation:{stock_id}:"):
                keys.extend(self._client.scan_iter(match=f"{prefix}*", count=100))
            if keys:
                self._client.delete(*keys)
        except RedisError:
            logger.warning("fundamental cache invalidation failed")

    def _read(self, key: str, model: type[BaseModel]) -> BaseModel | None:
        try:
            payload = self._client.get(key)
        except RedisError:
            logger.warning("fundamental cache read failed")
            return None
        if payload is None:
            return None
        try:
            return model.model_validate_json(payload)
        except ValueError:
            logger.warning("fundamental cache entry is invalid")
            return None

    def _write(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, value.model_dump_json())
        except RedisError:
            logger.warning("fundamental cache write failed")


def get_fundamental_cache() -> FundamentalCache:
    """Reuse one cache for the process. Redis is preferred when it answers."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        client = get_redis()
        client.ping()
        _cache = RedisFundamentalCache(client)
    except RedisError:
        logger.warning("Redis is unavailable; fundamentals are cached in-process until restart")
        _cache = MemoryFundamentalCache()
    return _cache
