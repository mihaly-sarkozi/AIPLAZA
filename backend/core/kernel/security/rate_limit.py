# backend/core/kernel/security/rate_limit.py
# Feladat: SlowAPI limitert, rate limit kulcsképzést és fallback throttle-t biztosít. Tenant+user/IP alapú kulcsokat használ, Redis storage-t választ, és érzékeny endpointokra dekorátor nélküli biztonsági throttlingot is ad memóriás fallbackkel. Core HTTP security helper, amelyet routerek és middleware regisztráció használ.
# Sárközi Mihály - 2026.05.21

import hashlib
import threading
import time
from collections import defaultdict, deque
from typing import Any

from core.infrastructure.cache.redis_client import get_redis
from core.kernel.config.config_loader import settings
from core.kernel.logging.observability import increment_metric


def _tenant_user_or_ip_key(request):
    """Rate limit kulcs: tenant + user vagy IP."""
    from slowapi.util import get_remote_address

    tenant = getattr(request.state, "tenant_slug", None) or ""
    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"t:{tenant}:user:{payload['sub']}"
    addr = get_remote_address(request)
    return f"t:{tenant}:ip:{addr}"


def user_or_ip_key(request):
    """Régi kompatibilitás: user vagy IP (tenant nélkül)."""
    from slowapi.util import get_remote_address

    payload = getattr(request.state, "user_token_payload", None)
    if payload and payload.get("sub"):
        return f"user:{payload['sub']}"
    return f"ip:{get_remote_address(request)}"


def _storage_uri():
    url = getattr(settings, "redis_url", None)
    if url and str(url).strip():
        return str(url).strip()
    return None


def get_limiter():
    from slowapi import Limiter

    limiter_kwargs: dict = {"key_func": _tenant_user_or_ip_key}
    storage = _storage_uri()
    if storage:
        limiter_kwargs["storage_uri"] = storage
    return Limiter(**limiter_kwargs)


class _LazyLimiterProxy:
    def __init__(self) -> None:
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            self._instance = get_limiter()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get_instance(), name)


limiter = _LazyLimiterProxy()


def get_rate_limit_redis():
    return get_redis()


def refresh_token_key(request):
    """Rate limit kulcs refresh végponthoz: tenant + session.

    A nyers refresh token nem kerülhet Redis kulcsba (keyspace/monitoring/dump
    szivárgás), ezért SHA-256 hash-t használunk.
    """
    from slowapi.util import get_remote_address

    tenant = getattr(request.state, "tenant_slug", None) or ""
    rt = request.cookies.get("refresh_token")
    if rt:
        digest = hashlib.sha256(rt.encode("utf-8")).hexdigest()
        return f"t:{tenant}:refresh:{digest}"
    return f"t:{tenant}:ip:{get_remote_address(request)}"


_fallback_lock = threading.Lock()
_fallback_buckets: dict[str, deque[float]] = defaultdict(deque)


def _bucket_allowed_memory(key: str, *, window_sec: int, max_requests: int) -> bool:
    now = time.monotonic()
    with _fallback_lock:
        bucket = _fallback_buckets[key]
        while bucket and now - bucket[0] > window_sec:
            bucket.popleft()
        if len(bucket) >= max_requests:
            return False
        bucket.append(now)
        return True


def _bucket_allowed_redis(key: str, *, window_sec: int, max_requests: int) -> bool | None:
    redis_client = get_redis()
    if redis_client is None:
        return None
    try:
        epoch_window = int(time.time() // window_sec)
        redis_key = f"rl:fallback:{key}:{epoch_window}"
        count = int(redis_client.incr(redis_key, 1) or 0)
        redis_client.expire(redis_key, window_sec + 3)
        return count <= max_requests
    except Exception:
        return None


def enforce_fallback_throttle(request: Any) -> tuple[bool, str]:
    """Fallback throttle olyan auth endpointokra, ahol nincs explicit limiter decorator."""
    path = str(getattr(getattr(request, "url", None), "path", "") or "")
    method = str(getattr(request, "method", "") or "").upper()
    sensitive_routes = {
        ("GET", "/api/auth/csrf-token"),
        ("POST", "/api/auth/authenticator/setup"),
        ("POST", "/api/auth/authenticator/confirm"),
        ("DELETE", "/api/auth/authenticator"),
        ("GET", "/api/platform-admin/auth/csrf-token"),
        ("GET", "/api/chat/ws-token"),
    }
    if (method, path) not in sensitive_routes:
        return True, ""
    tenant = str(getattr(getattr(request, "state", object()), "tenant_slug", "") or "")
    remote_ip = str(getattr(getattr(request, "client", None), "host", "") or "unknown")
    key = f"{tenant}:{remote_ip}:{method}:{path}"
    allowed = _bucket_allowed_redis(key, window_sec=60, max_requests=120)
    if allowed is None:
        allowed = _bucket_allowed_memory(key, window_sec=60, max_requests=120)
    if not allowed:
        increment_metric("rate_limit.reject_total", 1.0, tags={"endpoint": path, "scope": "fallback"})
        return False, "Too many requests."
    return True, ""


__all__ = [
    "enforce_fallback_throttle",
    "get_limiter",
    "get_rate_limit_redis",
    "limiter",
    "refresh_token_key",
    "user_or_ip_key",
]
