import json

import redis.asyncio as redis

from app.config import get_settings


class RedisClient:
    def __init__(self):
        self.settings = get_settings()
        self._redis: redis.Redis | None = None

    async def connect(self):
        if self._redis is None:
            self._redis = redis.from_url(
                self.settings.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._redis

    async def set(self, key: str, value: str, ex: int = 3600):
        r = await self.connect()
        await r.set(key, value, ex=ex)

    async def get(self, key: str) -> str | None:
        r = await self.connect()
        return await r.get(key)

    async def set_json(self, key: str, value: dict, ex: int = 3600):
        await self.set(key, json.dumps(value), ex)

    async def get_json(self, key: str) -> dict | None:
        data = await self.get(key)
        return json.loads(data) if data else None


redis_client = RedisClient()
