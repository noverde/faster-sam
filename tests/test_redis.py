import unittest
from unittest import mock
from faster_sam.cache.interface import CacheInterface

from faster_sam.cache.redis import RedisCache


class FakeRedis(CacheInterface):
    def __init__(self):
        self._db = {}

    def set(self, key, value, ttl):
        if isinstance(value, dict):
            raise Exception("A tuple item must be str, int, float or bytes.")
        self._db[key] = {"value": value, "ttl": ttl}

    def get(self, key):
        return self._db[key]["value"]

    def flushdb(self):
        self._db = {}


class TestRedis(unittest.TestCase):
    def setUp(self) -> None:
        self.redis_patch = mock.patch("faster_sam.cache.redis.redis")
        self.redis_mock = self.redis_patch.start()
        self.redis_mock.Redis.from_url.return_value = FakeRedis()
        self.key = "1234"

    def tearDown(self) -> None:
        RedisCache()._get_connection().flushdb()
        self.redis_patch.stop()

    def test_get_connection(self):
        cache = RedisCache()
        connection = cache._get_connection()

        self.assertIsNotNone(connection)
        self.assertIsInstance(connection, FakeRedis)

    def test_cache(self):
        cache = RedisCache()
        cache.set("123", "teste")
        payload = cache.get("123")

        self.assertIsNotNone(payload)
        self.assertEqual(payload, "teste")
