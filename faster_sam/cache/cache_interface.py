from abc import ABC, abstractmethod
from typing import Any


class CacheInterface(ABC):
    """
    Interface for cache backends.

    This abstract base class defines an interface for cache backends to implement.
    Subclasses must implement the `set` and `get` methods to provide functionality
    for setting and retrieving cached values.

    """

    @abstractmethod
    def set(self, key: Any, value: Any, ttl: Any) -> None:
        """
        Set a value in the cache.

        This method should be implemented by subclasses to set a value in the cache
        with the provided key and time-to-live (ttl).

        Parameters
        ----------
        key : Any
            The key under which the value will be stored in the cache.
        value : Any
            The value to be stored in the cache.
        ttl : Any
            The time-to-live (TTL) for the cached value. This parameter may have
            different types depending on the cache backend implementation.

        Returns
        -------
        None
        """
        pass  # pragma: no cover

    @abstractmethod
    def get(self, key: Any) -> Any:
        """
        Retrieve a value from the cache.

        This method should be implemented by subclasses to retrieve a value from the cache
        using the provided key.

        Parameters
        ----------
        key : Any
            The key associated with the value to retrieve from the cache.

        Returns
        -------
        Any
            The value associated with the given key if it exists in the cache, otherwise None.
        """
        pass  # pragma: no cover
