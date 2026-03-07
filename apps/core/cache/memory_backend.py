# apps/core/cache/memory_backend.py
# In-memory cache backend (egy worker / dev); Redis nélkül.
# 2026.03 - Sárközi Mihály

from __future__ import annotations

import threading
import time

from apps.core.cache.ports import CacheBackend


class MemoryCacheBackend(CacheBackend):
    """In-memory cache: (key -> (value, expiry_ts)). TTL alapú lejárat."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            if key not in self._store:
                return None
            val, expires = self._store[key]
            if time.monotonic() > expires:
                del self._store[key]
                return None
            return val

    def set(self, key: str, value: str, ttl_sec: int) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl_sec)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
