# apps/core/security/permissions_changed_store.py
# Rövid életű jel: role/is_active változás miatt ki léptettük a usert; refresh 401-nél ezt adjuk vissza.
# Központi tároló: REDIS_URL → Redis TTL key (több instance konzisztens); üres → in-memory TTL (dev).
# Ugyanaz a Redis kliens mint allowlist/rate limit (redis_client) – skálázás + biztonság.
# 2026.03 - Sárközi Mihály

from __future__ import annotations

import threading
import time

from apps.core.redis_client import get_redis

# Kulcs és TTL (Redis SETEX / in-memory expiry)
PERMISSIONS_CHANGED_TTL_SEC = 120
_KEY_PREFIX = "pc:"


def _key(tenant_slug: str | None, user_id: int) -> str:
    t = (tenant_slug or "").strip()
    return f"{_KEY_PREFIX}{t}:{user_id}"


# In-memory fallback: key -> expiry timestamp (monotonic)
_memory: dict[str, float] = {}
_memory_lock = threading.Lock()


def set(tenant_slug: str | None, user_id: int) -> None:
    """Role/is_active változás után: jel beállítása (refresh 401-nél „permissions_changed” válasz)."""
    k = _key(tenant_slug, user_id)
    r = get_redis()
    if r is not None:
        r.setex(k, PERMISSIONS_CHANGED_TTL_SEC, "1")
        return
    with _memory_lock:
        _memory[k] = time.monotonic() + PERMISSIONS_CHANGED_TTL_SEC


def get(tenant_slug: str | None, user_id: int) -> bool:
    """Refresh-nél: volt-e permissions change jel (401 reason = permissions_changed)."""
    k = _key(tenant_slug, user_id)
    r = get_redis()
    if r is not None:
        return r.get(k) is not None
    now = time.monotonic()
    with _memory_lock:
        expiry = _memory.get(k)
        if expiry is None or now >= expiry:
            _memory.pop(k, None)
            return False
        return True
