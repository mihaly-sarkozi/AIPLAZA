# apps/core/security/token_allowlist.py
# Bejelentkezett felhasználók access token jti-jainak tárolása: Redis vagy in-memory.
# Törlés/logout esetén remove_by_user → a token nem érvényes, middleware 401-et ad → frontend loginra dob.
# REDIS_URL beállítva → Redis SET per (tenant, user); üres → in-memory (dev).
# 2026.02 - Sárközi Mihály

from __future__ import annotations

import threading
from typing import Set

# In-memory fallback (ha nincs redis_url)
_store: dict[tuple[str | None, int], Set[str]] = {}
_lock = threading.Lock()

_redis_client = None
_redis_client_lock = threading.Lock()


def _get_redis():
    """Lazy Redis kliens (csak ha redis_url be van állítva)."""
    global _redis_client
    from config.settings import settings
    if not getattr(settings, "redis_url", None) or not settings.redis_url.strip():
        return None
    with _redis_client_lock:
        if _redis_client is None:
            import redis
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        return _redis_client


def _redis_key(tenant_slug: str | None, user_id: int) -> str:
    t = tenant_slug if tenant_slug is not None else ""
    return f"allowlist:{t}:{user_id}"


def _redis_ttl_seconds() -> int:
    """TTL másodpercben (access token élettartam + 1 perc)."""
    from config.settings import settings
    access_min = getattr(settings, "access_ttl_min", 15)
    return access_min * 60 + 60


def add(tenant_slug: str | None, user_id: int, jti: str) -> None:
    """Belépés/refresh után: az új access token jti-ját regisztráljuk."""
    r = _get_redis()
    if r is not None:
        key = _redis_key(tenant_slug, user_id)
        r.sadd(key, jti)
        r.expire(key, _redis_ttl_seconds())
        return
    with _lock:
        key = (tenant_slug, user_id)
        if key not in _store:
            _store[key] = set()
        _store[key].add(jti)


def remove_by_user(tenant_slug: str | None, user_id: int) -> None:
    """Kilépés vagy user törlés: a user összes access tokenjét érvénytelenítjük."""
    r = _get_redis()
    if r is not None:
        r.delete(_redis_key(tenant_slug, user_id))
        return
    with _lock:
        _store.pop((tenant_slug, user_id), None)


def is_allowed(tenant_slug: str | None, user_id: int, jti: str) -> bool:
    """Middleware: a token (jti) még az allowlistben van-e (nem léptettük ki / nem töröltük a usert)."""
    r = _get_redis()
    if r is not None:
        return bool(r.sismember(_redis_key(tenant_slug, user_id), jti))
    key = (tenant_slug, user_id)
    with _lock:
        return jti in _store.get(key, set())


def close_redis() -> None:
    """Lifespan shutdown: Redis kapcsolat bezárása."""
    global _redis_client
    with _redis_client_lock:
        if _redis_client is not None:
            try:
                _redis_client.close()
            except Exception:
                pass
            _redis_client = None
