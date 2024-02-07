from abc import ABC, abstractmethod
from typing import Any


class CacheInterface(ABC):
    @abstractmethod
    def set(self, key: Any, value: Any, ttl: Any) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def get(self, key: Any) -> Any:
        pass  # pragma: no cover
