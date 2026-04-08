import redis.asyncio as redis
import json
from app.core.config import settings

def _build_redis_url() -> str:
    """Build Redis URL from settings."""
    if settings.REDIS_URL:
        return settings.REDIS_URL
    if settings.REDIS_PASSWORD:
        return f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


class RedisClient:
    """
    Long-lived Redis client for the FastAPI process (lifespan-managed).
    NOT safe for Celery workers — use create_task_redis() instead.
    """
    def __init__(self):
        self.redis = None

    async def connect(self):
        if self.redis:
            return  # Already connected — idempotent
        self.redis = redis.from_url(
            _build_redis_url(),
            encoding="utf-8",
            decode_responses=True
        )

    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            self.redis = None

    async def ping(self):
        if not self.redis:
            await self.connect()
        return await self.redis.ping()

    async def get(self, key):
        if not self.redis:
            await self.connect()
        return await self.redis.get(key)

    async def set(self, key, value, ex=None):
        if not self.redis:
            await self.connect()
        return await self.redis.set(key, value, ex=ex)

    async def hgetall(self, key):
        if not self.redis:
            await self.connect()
        return await self.redis.hgetall(key)

    async def hset(self, key, mapping):
        if not self.redis:
            await self.connect()
        return await self.redis.hset(key, mapping=mapping)

    async def publish(self, channel, message):
        if not self.redis:
            await self.connect()
        payload = json.dumps(message) if not isinstance(message, str) else message
        return await self.redis.publish(channel, payload)

    async def subscribe(self, pattern: str):
        if not self.redis:
            await self.connect()
        pubsub = self.redis.pubsub()
        if '*' in pattern or '?' in pattern:
            await pubsub.psubscribe(pattern)
        else:
            await pubsub.subscribe(pattern)
        return pubsub

    async def expire(self, key, time):
        if not self.redis:
            await self.connect()
        return await self.redis.expire(key, time)

    async def delete(self, *keys):
        """Delete one or more keys from Redis"""
        if not self.redis:
            await self.connect()
        if keys:
            return await self.redis.delete(*keys)
        return 0


class TaskRedisClient:
    """
    Short-lived, task-scoped Redis client for Celery workers.
    Each Celery task should create one via create_task_redis(), use it,
    then close it in a finally block. This avoids the singleton-disconnect
    deadlock that occurs when multiple tasks share a single RedisClient
    across separate asyncio.run() calls.
    """
    def __init__(self):
        self.redis = redis.from_url(
            _build_redis_url(),
            encoding="utf-8",
            decode_responses=True
        )

    async def publish(self, channel, message):
        payload = json.dumps(message) if not isinstance(message, str) else message
        return await self.redis.publish(channel, payload)

    async def get(self, key):
        return await self.redis.get(key)

    async def set(self, key, value, ex=None):
        return await self.redis.set(key, value, ex=ex)

    async def hset(self, key, mapping):
        return await self.redis.hset(key, mapping=mapping)

    async def hgetall(self, key):
        return await self.redis.hgetall(key)

    async def expire(self, key, time):
        return await self.redis.expire(key, time)

    async def delete(self, *keys):
        """Delete one or more keys from Redis"""
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def close(self):
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception:
                pass
            try:
                await self.redis.connection_pool.disconnect()
            except Exception:
                pass
            self.redis = None


def create_task_redis() -> TaskRedisClient:
    """Factory: create a short-lived Redis connection for a single Celery task."""
    return TaskRedisClient()


# Global singleton — used only by the FastAPI process (lifespan-managed)
redis_client = RedisClient()
