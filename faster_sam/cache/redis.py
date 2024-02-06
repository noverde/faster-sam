import os
import redis
from faster_sam.cache.interface import CacheInterface


class RedisCache(CacheInterface):
    def __init__(self, url: str = os.getenv("CACHE_URL")) -> None:
        self._url = url
        self._connection = None

    def _get_connection(self):
        if not self._connection:
            self._connection = redis.Redis.from_url(url=self._url)

        return self._connection

    def set(self, key: str, value: str, ttl: int = os.getenv("CACHE_TTL", 900)):
        self._get_connection().set(key, value, ttl)

    def get(self, key: str):
        return self._get_connection().get(key)
