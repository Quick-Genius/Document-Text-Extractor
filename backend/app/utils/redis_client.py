import redis.asyncio as redis
import json
from app.core.config import settings

class RedisClient:
    def __init__(self):
        self.redis = None

    async def connect(self):
        # Use REDIS_URL if provided, otherwise construct from individual settings
        if settings.REDIS_URL:
            redis_url = settings.REDIS_URL
        else:
            if settings.REDIS_PASSWORD:
                redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            else:
                redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        
        self.redis = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

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
        # Redis pub/sub requires a string payload
        payload = json.dumps(message) if not isinstance(message, str) else message
        return await self.redis.publish(channel, payload)

    async def subscribe(self, pattern: str):
        if not self.redis:
            await self.connect()
        pubsub = self.redis.pubsub()
        # Use psubscribe for glob patterns (e.g. "progress:*"), subscribe for exact keys
        if '*' in pattern or '?' in pattern:
            await pubsub.psubscribe(pattern)
        else:
            await pubsub.subscribe(pattern)
        return pubsub

    async def expire(self, key, time):
        if not self.redis:
            await self.connect()
        return await self.redis.expire(key, time)

redis_client = RedisClient()
