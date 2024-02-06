from abc import ABC, abstractmethod


class CacheInterface(ABC):
    @abstractmethod
    def set(self, key: str, value: str, ttl: float) -> None:
        pass  # pragma: no cover

    @abstractmethod
    def get(self, key: str):
        pass  # pragma: no cover
