# Bejelentkezett felhasználók access token jti-jainak tárolása: Redis vagy in-memory.
# Törlés/logout esetén remove_by_user → a token nem érvényes, middleware 401-et ad → frontend loginra dob.
# REDIS_URL beállítva → Redis SET per (tenant, user); üres → in-memory (dev).
# Redis kliens: a cache capability redis kliense (kozponti, lifespan shutdown).
#
# HORIZONTÁLIS SKÁLÁZÁS – FIGYELMEZTETÉS:
# Az in-memory fallback CSAK fejlesztői / egypéldányos deploymentben biztonságos.
# Több web-process esetén a különböző processek saját memóriát tartanak:
#   - Ha a user X. processben jelentkezik ki, a többi process még érvényesnek látja a tokent.
#   - Ez biztonsági rés → multi-instance production módban REDIS_URL KÖTELEZŐ.
# Lásd: assert_redis_for_multi_instance() – AppContainer startup-kor hívódik.
# 2026.02 - Sárközi Mihály

from __future__ import annotations

import logging
import threading
from typing import Set

from core.capabilities.cache.redis_client import get_redis

_log = logging.getLogger(__name__)

# In-memory fallback (ha nincs redis_url) – egypéldányos / dev mód
_store: dict[tuple[str | None, int], Set[str]] = {}
_lock = threading.Lock()


def assert_redis_for_multi_instance() -> None:
    """Startup guard: több web-process esetén Redis kötelező.

    Ha REDIS_URL nincs beállítva és az INSTANCE_ROLE=web (vagy a prod env
    azt jelzi, hogy több példány fut), CRITICAL üzenettel figyelmeztet.
    A token allowlist in-memory fallback-kel NEM biztonságos multi-instance-ban:
    kilépés / token visszavonás csak az adott processben érvényes.
    """
    r = get_redis()
    if r is not None:
        return  # Redis elérhető, minden rendben

    try:
        import os
        env = os.getenv("APP_ENV", "dev").lower()
        from core.kernel.config.instance_role import InstanceRole, get_instance_role
        role = get_instance_role()
    except Exception:
        return  # Ha a konfiguráció még nem töltődött be, nem blokkoljuk

    if env == "prod" or role == InstanceRole.WEB:
        _log.critical(
            "TOKEN ALLOWLIST BIZTONSÁGI FIGYELMEZTETÉS: "
            "REDIS_URL nincs beállítva, de az alkalmazás production/web módban fut. "
            "Az in-memory token allowlist NEM BIZTONSÁGOS több web-process esetén: "
            "kilépés és token visszavonás csak az adott processben érvényes. "
            "Állítsd be a REDIS_URL-t és indítsd újra a rendszert."
        )


# Ez a függvény a(z) redis_key logikáját valósítja meg.
def _redis_key(tenant_slug: str | None, user_id: int) -> str:
    t = tenant_slug if tenant_slug is not None else ""
    return f"allowlist:{t}:{user_id}"


def _redis_ttl_seconds() -> int:
    """TTL másodpercben (access token élettartam + 1 perc)."""
    from core.kernel.config.config_loader import settings
    access_min = getattr(settings, "access_ttl_min", 15)
    return access_min * 60 + 60


def add(tenant_slug: str | None, user_id: int, jti: str) -> None:
    """Belépés/refresh után: az új access token jti-ját regisztráljuk."""
    r = get_redis()
    if r is not None:
        try:
            key = _redis_key(tenant_slug, user_id)
            r.sadd(key, jti)
            r.expire(key, _redis_ttl_seconds())
            return
        except Exception as e:
            _log.warning("allowlist add: Redis failed, falling back to in-memory: %s", e)
    with _lock:
        key = (tenant_slug, user_id)
        if key not in _store:
            _store[key] = set()
        _store[key].add(jti)


def remove_by_user(tenant_slug: str | None, user_id: int) -> None:
    """Kilépés vagy user törlés: a user összes access tokenjét érvénytelenítjük."""
    r = get_redis()
    if r is not None:
        try:
            r.delete(_redis_key(tenant_slug, user_id))
            return
        except Exception as e:
            _log.warning("allowlist remove_by_user: Redis failed, clearing in-memory: %s", e)
    with _lock:
        _store.pop((tenant_slug, user_id), None)


def is_allowed(tenant_slug: str | None, user_id: int, jti: str) -> bool:
    """Middleware: a token (jti) még az allowlistben van-e (nem léptettük ki / nem töröltük a usert)."""
    r = get_redis()
    if r is not None:
        try:
            return bool(r.sismember(_redis_key(tenant_slug, user_id), jti))
        except Exception as e:
            _log.warning("allowlist is_allowed: Redis failed, checking in-memory: %s", e)
    key = (tenant_slug, user_id)
    with _lock:
        return jti in _store.get(key, set())


