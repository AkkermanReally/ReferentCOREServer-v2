# rcs/utils/redis_client.py
import redis.asyncio as redis
from rcs.settings import settings

# Create a connection pool that will be shared across the application
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True
)

def get_redis_client() -> redis.Redis:
    """Returns a Redis client instance from the shared connection pool."""
    return redis.Redis(connection_pool=redis_pool)
