# apps/core/cache/ports.py
# Központi cache interface – worker/instance független viselkedés (Redis vagy memory).
# 2026.03 - Sárközi Mihály

from __future__ import annotations

from abc import ABC, abstractmethod


class CacheBackend(ABC):
    """Cache backend interface: get/set/delete, TTL másodpercben. Értékek stringek (pl. JSON)."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Kulcs alapján érték; nincs vagy lejárt → None."""
        ...

    @abstractmethod
    def set(self, key: str, value: str, ttl_sec: int) -> None:
        """Érték tárolása TTL másodperccel."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Kulcs törlése."""
        ...
