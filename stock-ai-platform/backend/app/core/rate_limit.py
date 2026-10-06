import logging
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Counts attempts inside a time window. Redis is not the user store."""

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        raise NotImplementedError


class RedisRateLimiter(RateLimiter):
    def __init__(self, client: Redis) -> None:
        self._client = client

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        namespaced = f"ratelimit:{key}"
        count = int(self._client.incr(namespaced))
        if count == 1:
            self._client.expire(namespaced, window_seconds)
        return count <= limit


class MemoryRateLimiter(RateLimiter):
    """Process-local limiter used by tests."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        recent = [stamp for stamp in self._events[key] if now - stamp < window_seconds]
        if len(recent) >= limit:
            self._events[key] = recent
            return False
        recent.append(now)
        self._events[key] = recent
        return True


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Use Redis when it answers. Otherwise limit inside this process."""
    global _limiter
    if _limiter is not None:
        return _limiter
    try:
        client = get_redis()
        client.ping()
        _limiter = RedisRateLimiter(client)
    except RedisError:
        logger.warning("Redis is unavailable; authentication rate limits are in-process until restart")
        _limiter = MemoryRateLimiter()
    return _limiter


def limit_auth(action: str, limit_attr: str, window_attr: str) -> Callable[..., None]:
    def dependency(
        request: Request,
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        client_host = request.client.host if request.client is not None else "unknown"
        limit = int(getattr(settings, limit_attr))
        window = int(getattr(settings, window_attr))
        try:
            allowed = limiter.hit(f"auth:{action}:{client_host}", limit, window)
        except RedisError:
            logger.exception("Authentication rate limiter is unavailable")
            raise HTTPException(status_code=503, detail="Service temporarily unavailable") from None
        if not allowed:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")

    return dependency
