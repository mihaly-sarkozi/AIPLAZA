# backend/core/modules/tenant/signup/abuse_controls.py
# Feladat: Demo signup visszaélés-védelmi helper logikát tartalmaz. Napi számlálókat, engedélyezési flaget és limit ellenőrzést kezel cache/settings alapon. Tenant signup abuse control réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import threading

from core.infrastructure.cache.redis_client import get_redis
from core.kernel.config.config_loader import settings
from core.kernel.config.config_loader import get_app_env
from core.kernel.config.environment import is_deployed_env

_SIGNUP_ENABLED_KEY = "security:demo_signup:enabled"
_COUNTER_PREFIX = "security:demo_signup:counter"
_COUNTER_TTL_SEC = 3 * 24 * 60 * 60
_fallback_lock = threading.RLock()
_fallback_counters: dict[str, int] = defaultdict(int)
_fallback_enabled_override: bool | None = None


def _fail_closed_active() -> bool:
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    return is_deployed_env(env) and bool(getattr(settings, "demo_signup_fail_closed_without_redis", True))


def is_demo_signup_enabled(*, default_enabled: bool = True) -> bool:
    redis_client = get_redis()
    fail_closed = _fail_closed_active()
    if redis_client is None and fail_closed:
        return False
    if redis_client is not None:
        try:
            value = redis_client.get(_SIGNUP_ENABLED_KEY)
            if value is None:
                return bool(default_enabled)
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            if fail_closed:
                return False
            pass
    with _fallback_lock:
        if _fallback_enabled_override is None:
            return bool(default_enabled)
        return bool(_fallback_enabled_override)


def set_demo_signup_enabled(enabled: bool) -> None:
    normalized = bool(enabled)
    redis_client = get_redis()
    fail_closed = _fail_closed_active()
    if redis_client is None and fail_closed:
        raise RuntimeError("Demo signup control szolgáltatás átmenetileg nem elérhető.")
    if redis_client is not None:
        try:
            redis_client.set(_SIGNUP_ENABLED_KEY, "1" if normalized else "0")
            return
        except Exception:
            if fail_closed:
                raise RuntimeError("Demo signup control szolgáltatás átmenetileg nem elérhető.")
            pass
    global _fallback_enabled_override
    with _fallback_lock:
        _fallback_enabled_override = normalized


def bump_daily_counter(*, scope: str, key: str, now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    day_key = current.astimezone(timezone.utc).strftime("%Y%m%d")
    normalized_scope = (scope or "").strip().lower() or "global"
    normalized_key = (key or "").strip().lower() or "default"
    counter_key = f"{_COUNTER_PREFIX}:{day_key}:{normalized_scope}:{normalized_key}"

    redis_client = get_redis()
    fail_closed = _fail_closed_active()
    if redis_client is None and fail_closed:
        raise RuntimeError("Demo signup rate-limit szolgáltatás átmenetileg nem elérhető.")
    if redis_client is not None:
        try:
            count = int(redis_client.incr(counter_key))
            if int(redis_client.ttl(counter_key) or -1) < 0:
                redis_client.expire(counter_key, _COUNTER_TTL_SEC)
            return count
        except Exception:
            if fail_closed:
                raise RuntimeError("Demo signup rate-limit szolgáltatás átmenetileg nem elérhető.")
            pass

    with _fallback_lock:
        _fallback_counters[counter_key] = int(_fallback_counters.get(counter_key, 0)) + 1
        return _fallback_counters[counter_key]


__all__ = [
    "bump_daily_counter",
    "is_demo_signup_enabled",
    "set_demo_signup_enabled",
]
