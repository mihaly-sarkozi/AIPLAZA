# apps/core/cache/redis_backend.py
# Redis cache backend – több worker/instance esetén konzisztens.
# 2026.03 - Sárközi Mihály

from __future__ import annotations

from apps.core.cache.ports import CacheBackend


class RedisCacheBackend(CacheBackend):
    """Redis cache: get/set/delete, TTL. decode_responses=True → string."""

    def __init__(self, redis_client) -> None:
        self._r = redis_client

    def get(self, key: str) -> str | None:
        val = self._r.get(key)
        return val if isinstance(val, str) else (val.decode("utf-8") if val else None)

    def set(self, key: str, value: str, ttl_sec: int) -> None:
        self._r.setex(key, ttl_sec, value)

    def delete(self, key: str) -> None:
        self._r.delete(key)
