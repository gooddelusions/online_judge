from abc import ABC, abstractmethod


class ProxyProvider(ABC):
    @abstractmethod
    def list_all(self) -> list[str]:
        """Return proxy URLs as strings usable directly in httpx (http://user:pass@host:port)."""
        ...
