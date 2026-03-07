# apps/core/security/permissions_changed_store.py
# Rövid életű jel: role/is_active változás miatt ki léptettük a usert; refresh 401-nél ezt adjuk vissza.
# In-memory (tenant_slug, user_id) -> timestamp; TTL 120 sec.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations

import threading
import time

_store: dict[tuple[str | None, int], float] = {}
_lock = threading.Lock()
_TTL_SEC = 120


def set(tenant_slug: str | None, user_id: int) -> None:
    with _lock:
        key = (tenant_slug, user_id)
        _store[key] = time.monotonic()


def get(tenant_slug: str | None, user_id: int) -> bool:
    with _lock:
        key = (tenant_slug, user_id)
        if key not in _store:
            return False
        if time.monotonic() - _store[key] > _TTL_SEC:
            del _store[key]
            return False
        return True
