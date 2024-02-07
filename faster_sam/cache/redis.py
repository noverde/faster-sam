import os
from typing import Optional
from redis import Redis
from faster_sam.cache.interface import CacheInterface


CACHE_TTL = os.getenv("FASTER_SAM_CACHE_TTL", 900)
CACHE_URL = os.getenv("FASTER_SAM_CACHE_URL")


class RedisCache(CacheInterface):
    _connection: Optional[Redis] = None

    @property
    def connection(self) -> Redis:
        if self._connection is None:
            self._connection = Redis.from_url(url=CACHE_URL)

        return self._connection

    def set(self, key: str, value: str, ttl: int = CACHE_TTL):
        self.connection.set(key, value, ttl)

    def get(self, key: str):
        return self.connection.get(key)
