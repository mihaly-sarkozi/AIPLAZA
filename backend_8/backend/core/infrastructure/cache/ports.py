# backend/core/infrastructure/cache/ports.py
# Feladat: A cache backendek közös contractját definiálja. Get, set és delete műveleteket ír elő string értékekhez és másodperc alapú TTL-hez, hogy Redis és in-memory adapter azonos felületet adjon. Cache port réteg a modulok és backend implementációk között.
# Sárközi Mihály - 2026.05.21

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
