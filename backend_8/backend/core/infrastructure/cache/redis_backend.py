# backend/core/infrastructure/cache/redis_backend.py
# Feladat: Redis alapú CacheBackend adaptert valósít meg. A közös get/set/delete contractot Redis get, setex és delete műveletekre fordítja, több worker vagy több instance közti megosztott cache használatához. Redis adapter a magasabb szintű cache helper réteg alatt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.infrastructure.cache.ports import CacheBackend


class RedisCacheBackend(CacheBackend):
    """Redis cache: get/set/delete, TTL. decode_responses=True → string."""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, redis_client) -> None:
        self._r = redis_client

    # Ez a metódus visszaadja a(z) get logikáját.
    def get(self, key: str) -> str | None:
        val = self._r.get(key)
        return val if isinstance(val, str) else (val.decode("utf-8") if val else None)

    # Ez a metódus beállítja a(z) set logikáját.
    def set(self, key: str, value: str, ttl_sec: int) -> None:
        self._r.setex(key, ttl_sec, value)

    # Ez a metódus törli a(z) delete logikáját.
    def delete(self, key: str) -> None:
        self._r.delete(key)
