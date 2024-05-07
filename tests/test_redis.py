import unittest
from unittest import mock

from faster_sam.cache import redis_cache
from faster_sam.cache.cache_interface import CacheInterface
from faster_sam.cache.redis_cache import RedisCache


class FakeRedis(CacheInterface):
    def __init__(self):
        self._db = {}
        self.connected = False

    def disconnect(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True

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
        redis_cache.CACHE_URL = "redis://127.0.0.1:6379/0"

        self.redis_patch = mock.patch("faster_sam.cache.redis_cache.Redis")
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

    @mock.patch.object(RedisCache, "reconnect")
    @mock.patch.object(FakeRedis, "set", side_effect=ConnectionError)
    def test_set_cache_exception(self, mock_set, mock_reconnect):
        cache = RedisCache()
        cache.set("123", "teste", 900)

        self.assertEqual(cache.get("123"), None)
        mock_set.assert_called_once()
        mock_reconnect.assert_not_called()

    @mock.patch.object(RedisCache, "reconnect")
    @mock.patch.object(FakeRedis, "get", side_effect=ConnectionError)
    def test_get_cache_exception(self, mock_get, mock_reconnect):
        cache = RedisCache()
        cache.set("123", "teste", 900)
        response = cache.get("123")

        self.assertEqual(response, None)
        self.assertEqual(mock_get.call_count, 2)
        mock_reconnect.assert_called_once()

    def test_reconnect(self):
        cache = RedisCache()
        cache.reconnect()

        self.assertTrue(cache.connection.connected)

    def test_cache_not_exists(self):
        cache = RedisCache()
        payload = cache.get("1234")

        self.assertIsNone(payload)

    def test_cache_value_invalid_type(self):
        cache = RedisCache()

        with self.assertRaises(TypeError):
            cache.set("123", {"key": "value"})
