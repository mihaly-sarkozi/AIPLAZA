# backend/core/infrastructure/cache/memory_backend.py
# Feladat: Thread-safe in-memory CacheBackend implementációt ad. Kulcsonként string értéket és monotonic időn alapuló lejáratot tárol, Redis nélküli dev/test vagy fallback működéshez. Egy processre korlátozott cache adapter, nem több worker közti megosztott storage.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import threading
import time

from core.infrastructure.cache.ports import CacheBackend


class MemoryCacheBackend(CacheBackend):
    """In-memory cache: (key -> (value, expiry_ts)). TTL alapú lejárat."""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    # Ez a metódus visszaadja a(z) get logikáját.
    def get(self, key: str) -> str | None:
        with self._lock:
            if key not in self._store:
                return None
            val, expires = self._store[key]
            if time.monotonic() > expires:
                del self._store[key]
                return None
            return val

    # Ez a metódus beállítja a(z) set logikáját.
    def set(self, key: str, value: str, ttl_sec: int) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl_sec)

    # Ez a metódus törli a(z) delete logikáját.
    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
