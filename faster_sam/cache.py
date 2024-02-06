from enum import Enum
import os
from abc import ABC, abstractmethod

try:
    import redis
except ImportError:
    pass


class Cache(Enum):
    REDIS = "redis"


class CacheInterface(ABC):
    @abstractmethod
    def _get_connection(self):
        pass  # pragma: no cover

    @abstractmethod
    def set(self, key: str, value: str, ttl: float) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def get(self, key: str):
        pass  # pragma: no cover

    @abstractmethod
    def set_key(self, headers: dict):
        pass  # pragma: no cover


class RedisCache(CacheInterface):
    def __init__(self) -> None:
        self._token = None
        self._connection = None

    @property
    def token(self) -> hash:
        return self._token

    def _get_connection(self):
        if not self._connection:
            self._connection = redis.Redis.from_url(url=os.getenv("CACHE_URL"))

        return self._connection

    def set(self, key: str, value: str, ttl: float):
        self._get_connection().set(self.token, value, ttl)

    def get(self):
        return self._get_connection().get(self.token)

    def set_key(self, headers: dict) -> None:
        headers = {key.lower(): value for key, value in headers.items()}

        if "AUTHORIZATION" in os.environ:
            self._token = os.environ["AUTHORIZATION"]
        else:
            self._token = headers.get("authorization", headers.get("x-api-key"))


def factory(cache: str) -> CacheInterface:
    caches = {Cache.REDIS: RedisCache}
    key = Cache(cache)

    return caches[key]()
