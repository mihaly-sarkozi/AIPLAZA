# backend/core/modules/auth/repository/token_allowlist.py
# Feladat: Access token JTI allowlist tárolást biztosít Redis vagy fejlesztői in-memory fallback segítségével. Login és refresh után regisztrálja az új JTI-t, logout vagy user változás után törli, a middleware pedig ezen keresztül érvényteleníti a tokeneket. Auth runtime repository helper, production többpéldányos módban Redis használata szükséges.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import threading
from typing import Set

from core.infrastructure.cache.redis_client import get_redis
from core.kernel.config.config_loader import settings
from core.kernel.config.config_loader import get_app_env
from core.kernel.config.environment import is_deployed_env, normalize_app_env

_log = logging.getLogger(__name__)

# In-memory fallback (ha nincs redis_url) – egypéldányos / dev mód
_store: dict[tuple[str | None, int], Set[str]] = {}
_lock = threading.Lock()


class TokenAllowlistUnavailableError(RuntimeError):
    pass


def _fail_closed_active() -> bool:
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    return is_deployed_env(env) and bool(getattr(settings, "token_allowlist_fail_closed_without_redis", True))


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
        env = normalize_app_env(os.getenv("APP_ENV", "local"))
        from core.kernel.runtime.instance_role import InstanceRole, get_instance_role
        role = get_instance_role()
    except Exception:
        return  # Ha a konfiguráció még nem töltődött be, nem blokkoljuk

    if is_deployed_env(env) or role == InstanceRole.WEB:
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
    fail_closed = _fail_closed_active()
    if r is None and fail_closed:
        raise TokenAllowlistUnavailableError("Token allowlist szolgáltatás átmenetileg nem elérhető.")
    if r is not None:
        try:
            key = _redis_key(tenant_slug, user_id)
            r.sadd(key, jti)
            r.expire(key, _redis_ttl_seconds())
            return
        except Exception as e:
            if fail_closed:
                raise TokenAllowlistUnavailableError("Token allowlist szolgáltatás átmenetileg nem elérhető.") from e
            _log.warning("allowlist add: Redis failed, falling back to in-memory: %s", e)
    with _lock:
        key = (tenant_slug, user_id)
        if key not in _store:
            _store[key] = set()
        _store[key].add(jti)


def remove_by_user(tenant_slug: str | None, user_id: int) -> None:
    """Kilépés vagy user törlés: a user összes access tokenjét érvénytelenítjük."""
    r = get_redis()
    fail_closed = _fail_closed_active()
    if r is None and fail_closed:
        return
    if r is not None:
        try:
            r.delete(_redis_key(tenant_slug, user_id))
            return
        except Exception as e:
            if fail_closed:
                return
            _log.warning("allowlist remove_by_user: Redis failed, clearing in-memory: %s", e)
    with _lock:
        _store.pop((tenant_slug, user_id), None)


def is_allowed(tenant_slug: str | None, user_id: int, jti: str) -> bool:
    """Middleware: a token (jti) még az allowlistben van-e (nem léptettük ki / nem töröltük a usert)."""
    r = get_redis()
    fail_closed = _fail_closed_active()
    if r is None and fail_closed:
        return False
    if r is not None:
        try:
            return bool(r.sismember(_redis_key(tenant_slug, user_id), jti))
        except Exception as e:
            if fail_closed:
                return False
            _log.warning("allowlist is_allowed: Redis failed, checking in-memory: %s", e)
    key = (tenant_slug, user_id)
    with _lock:
        return jti in _store.get(key, set())


