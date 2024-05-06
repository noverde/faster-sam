import logging
import os
from typing import Optional

from redis import Redis

from faster_sam.cache.cache_interface import CacheInterface

logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("FASTER_SAM_CACHE_TTL", 900))
CACHE_URL = os.getenv("FASTER_SAM_CACHE_URL", "")


class RedisCache(CacheInterface):
    """
    A cache backend implementation using Redis.

    This class implements the CacheInterface and provides functionality
    for setting and retrieving cached values using Redis as the underlying
    cache storage.

    e.g

    Example of usage.

    >>> cache = RedisCache()
    >>> cache.set("my-key", "my-value")
    >>> cache.get("my-key")

    Environment Variables
    ---------------------
    FASTER_SAM_CACHE_TTL : int
        The time-to-live (TTL) for the cached values. This
        variable specifies the duration in seconds for which cached values will remain valid.
        For example, setting this variable to 900 would make cached values expire after 15 minutes.

    FASTER_SAM_CACHE_URL : str
        The URL specifying the connection string that should contain the URL used
        to establish a connection to the Redis server where the cache is hosted.
        The URL format should follow the standard Redis connection string format like:
        redis://127.0.0.1:6379/0
    """

    _connection: Optional[Redis] = None

    @property
    def connection(self) -> Redis:
        """
        Lazily initializes and returns the Redis connection object.

        If the connection has not been initialized yet, it will be created
        using the Redis URL specified in the environment variable `CACHE_URL`.

        Returns
        -------
        Redis
            The Redis connection object.
        """
        if self._connection is None:
            self._connection = Redis.from_url(url=CACHE_URL)

        return self._connection

    def reconnect(self) -> None:
        """
        Reconnect to the Redis server.

        This method is used to re-establish a connection to the Redis server
        in case the connection is lost.

        Returns
        -------
        None
        """
        self.connection.disconnect()
        self.connection.connect()

    def set(self, key: str, value: str, ttl: int = CACHE_TTL) -> None:
        """
        Set a value in the Redis cache.

        Parameters
        ----------
        key : str
            The key under which the value will be stored in the Redis cache.
        value : str
            The value to be stored in the Redis cache.
        ttl : int, optional
            The time-to-live (TTL) for the cached value in seconds.
            The value is specified by `CACHE_TTL` constant with 900
            seconds as default value if not provided.

        Returns
        -------
        None
        """
        try:
            self.connection.set(key, value, ttl)
        except ConnectionError:
            logger.info("Failed to connect to Redis server.")

    def get(self, key: str, retry: int = 1) -> Optional[str]:
        """
        Retrieve a value from the Redis cache.

        Parameters
        ----------
        key : str
            The key associated with the value to retrieve from the Redis cache.

        Returns
        -------
        str or None
            The value associated with the given key if it exists in the cache,
            otherwise None.
        """
        if retry > 0:
            try:
                return self.connection.get(key)
            except ConnectionError:
                RedisCache.reconnect()
                return self.get(key, retry - 1)

        logger.info("Failed to connect to Redis server.")
        return None
