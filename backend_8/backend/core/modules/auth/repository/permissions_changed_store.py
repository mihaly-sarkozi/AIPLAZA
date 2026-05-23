# backend/core/modules/auth/repository/permissions_changed_store.py
# Feladat: Rövid életű jelzést tárol arról, hogy egy user jogosultságai megváltoztak. Redis vagy in-memory fallback segítségével jelzi a refresh flow számára, hogy új token kiadás előtt a jogosultságváltozást figyelembe kell venni. Auth runtime repository helper többpéldányos környezetben Redis ajánlással.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import threading
import time

from core.infrastructure.cache.redis_client import get_redis
from core.kernel.config.environment import is_deployed_env, normalize_app_env

_log = logging.getLogger(__name__)

PERMISSIONS_CHANGED_TTL_SEC = 120
_KEY_PREFIX = "pc:"


def _key(tenant_slug: str | None, user_id: int) -> str:
    tenant = (tenant_slug or "").strip()
    return f"{_KEY_PREFIX}{tenant}:{user_id}"


_memory: dict[str, float] = {}
_memory_lock = threading.Lock()


def set(tenant_slug: str | None, user_id: int) -> None:
    key = _key(tenant_slug, user_id)
    redis = get_redis()
    if redis is not None:
        redis.setex(key, PERMISSIONS_CHANGED_TTL_SEC, "1")
        return
    with _memory_lock:
        _memory[key] = time.monotonic() + PERMISSIONS_CHANGED_TTL_SEC


def get(tenant_slug: str | None, user_id: int) -> bool:
    key = _key(tenant_slug, user_id)
    redis = get_redis()
    if redis is not None:
        return redis.get(key) is not None
    now = time.monotonic()
    with _memory_lock:
        expiry = _memory.get(key)
        if expiry is None or now >= expiry:
            _memory.pop(key, None)
            return False
        return True


def assert_redis_for_multi_instance() -> None:
    """Startup guard: több web-process esetén Redis kötelező.

    Redis nélkül a jogosultságváltozás csak az adott processben jelenik meg;
    a többi process a régi engedélyekkel dolgozik tovább. Ez nem biztonsági rés
    (a token allowlist kezeli a logout-ot), de a jogosultságfrissítés lassabb.
    Multi-instance production módban erősen ajánlott a REDIS_URL beállítása.
    """
    r = get_redis()
    if r is not None:
        return

    try:
        import os
        env = normalize_app_env(os.getenv("APP_ENV", "local"))
        from core.kernel.runtime.instance_role import InstanceRole, get_instance_role
        role = get_instance_role()
    except Exception:
        return

    if is_deployed_env(env) or role == InstanceRole.WEB:
        _log.warning(
            "PERMISSIONS CHANGED STORE: REDIS_URL nincs beállítva, de az alkalmazás "
            "production/web módban fut. Több web-process esetén a jogosultságváltozás "
            "csak az adott processben érvényes azonnal. "
            "Ajánlott: állítsd be a REDIS_URL-t a konzisztens jogosultságkezeléshez."
        )
