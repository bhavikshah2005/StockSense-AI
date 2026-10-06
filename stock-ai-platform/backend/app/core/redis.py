from redis import Redis

from app.core.config import settings


def get_redis() -> Redis:
    """Create a Redis client from REDIS_URL.

    Authentication rate limits use this client. User accounts stay in PostgreSQL.
    """
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
