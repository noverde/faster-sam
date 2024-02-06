import unittest
from unittest import mock

from faster_sam.cache.redis import RedisCache


class TestRedis(unittest.TestCase):
    def setUp(self) -> None:
        self.redis_patch = mock.patch("faster_sam.cache.redis.redis")
        self.redis_mock = self.redis_patch.start()
        self._connection = self.redis_mock.Redis.from_url.return_value
        self.key = "1234"

    def tearDown(self) -> None:
        self.redis_patch.stop()

    def test_get_connection(self):
        cache = RedisCache()
        connection = cache._get_connection()
        self.assertIsNotNone(connection)
        self.assertEqual(connection, self._connection)
        
    def test_get(self):
        cache = RedisCache()
        cache.get(self.key)

        self._connection.get.assert_called_once_with(self.key)

    def test_set(self):
        cache = RedisCache()
        cache.set(self.key, "test")

        self._connection.set.assert_called_once_with(self.key, "test", 900)
