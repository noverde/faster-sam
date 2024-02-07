import unittest
from unittest import mock
from faster_sam.cache import redis
from faster_sam.cache.interface import CacheInterface

from faster_sam.cache.redis import RedisCache


class FakeRedis(CacheInterface):
    def __init__(self):
        self._db = {}

    def set(self, key, value, ttl):
        if isinstance(value, dict):
            raise TypeError("A tuple item must be str, int, float or bytes.")
        self._db[key] = {"value": value, "ttl": ttl}

    def get(self, key):
        return self._db.get(key, {}).get("value")

    def flushdb(self):
        self._db = {}


class TestRedis(unittest.TestCase):
    def setUp(self) -> None:
        redis.CACHE_URL = "redis://127.0.0.1:6379/0"

        self.redis_patch = mock.patch("faster_sam.cache.redis.Redis")
        self.redis_mock = self.redis_patch.start()
        self.redis_mock.from_url.return_value = FakeRedis()
        self.key = "1234"

    def tearDown(self) -> None:
        RedisCache().connection.flushdb()
        self.redis_patch.stop()

    def test_get_connection(self):
        cache = RedisCache()
        connection = cache.connection

        self.assertIsNotNone(connection)
        self.assertIsInstance(connection, FakeRedis)

    def test_cache(self):
        cache = RedisCache()
        cache.set("123", "teste")
        payload = cache.get("123")

        self.assertIsNotNone(payload)
        self.assertEqual(payload, "teste")

    def test_cache_not_exists(self):
        cache = RedisCache()
        payload = cache.get("1234")

        self.assertIsNone(payload)

    def test_cache_value_invalid_type(self):
        cache = RedisCache()

        with self.assertRaises(TypeError):
            cache.set("123", {"key": "value"})
