# backend/apps/chat/router/websocket_limits.py
# Feladat: Chat websocket rate limit és kapcsolat concurrency helper logikát tartalmaz. Redis alapú és in-memory fallback bucketeket, tenant/user connection limiteket és websocket beállítás olvasást választ le a chat routerről. Program-specifikus websocket guard réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import threading
from collections import deque
from time import monotonic

from core.kernel.config.config_loader import settings
from core.kernel.security.rate_limit import get_rate_limit_redis

WS_BURST_WINDOW_SEC = 10
ws_lock = threading.Lock()
ws_fallback_buckets: dict[str, deque[float]] = {}
ws_connections_lock = threading.Lock()
ws_connection_counts: dict[str, int] = {}


def ws_limit_per_10s() -> int:
    return max(1, int(getattr(settings, "ws_chat_max_messages_per_10s", 20) or 20))


def ws_idle_timeout_sec() -> int:
    return max(5, int(getattr(settings, "ws_chat_idle_timeout_sec", 45) or 45))


def ws_max_message_chars() -> int:
    return max(256, int(getattr(settings, "ws_chat_max_message_chars", 8000) or 8000))


def ws_enabled() -> bool:
    return bool(getattr(settings, "enable_chat_websocket", False))


def ws_max_connections_per_tenant() -> int:
    return max(1, int(getattr(settings, "ws_chat_max_connections_per_tenant", 20) or 20))


def ws_max_connections_per_user() -> int:
    return max(1, int(getattr(settings, "ws_chat_max_connections_per_user", 3) or 3))


def ws_rate_limit_key(*, tenant_slug: str | None, user_id: int | None, remote_ip: str | None) -> str:
    tenant_part = str(tenant_slug or "").strip().lower() or "_"
    actor = f"user:{int(user_id)}" if user_id else f"ip:{str(remote_ip or '').strip() or 'unknown'}"
    return f"ws:{tenant_part}:{actor}"


def ws_allow_message(*, tenant_slug: str | None, user_id: int | None, remote_ip: str | None) -> bool:
    key = ws_rate_limit_key(tenant_slug=tenant_slug, user_id=user_id, remote_ip=remote_ip)
    now = monotonic()
    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        window_bucket = int(now // WS_BURST_WINDOW_SEC)
        redis_key = f"rl:{key}:{window_bucket}"
        try:
            count = int(redis_client.incr(redis_key, 1) or 0)
            redis_client.expire(redis_key, WS_BURST_WINDOW_SEC + 3)
            return count <= ws_limit_per_10s()
        except Exception:
            pass
    with ws_lock:
        bucket = ws_fallback_buckets.get(key) or deque()
        while bucket and now - bucket[0] > WS_BURST_WINDOW_SEC:
            bucket.popleft()
        if len(bucket) >= ws_limit_per_10s():
            ws_fallback_buckets[key] = bucket
            return False
        bucket.append(now)
        ws_fallback_buckets[key] = bucket
    return True


def ws_connection_keys(*, tenant_slug: str | None, user_id: int | None) -> tuple[str, str]:
    tenant_key = str(tenant_slug or "").strip().lower() or "_"
    user_key = str(int(user_id or 0))
    return (
        f"ws:conn:tenant:{tenant_key}",
        f"ws:conn:user:{tenant_key}:{user_key}",
    )


def ws_try_acquire_connection(*, tenant_slug: str | None, user_id: int | None) -> tuple[bool, str, dict[str, str] | None]:
    tenant_conn_key, user_conn_key = ws_connection_keys(tenant_slug=tenant_slug, user_id=user_id)
    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        try:
            tenant_count = int(redis_client.incr(tenant_conn_key, 1) or 0)
            user_count = int(redis_client.incr(user_conn_key, 1) or 0)
            redis_client.expire(tenant_conn_key, 3600)
            redis_client.expire(user_conn_key, 3600)
            if tenant_count > ws_max_connections_per_tenant():
                redis_client.decr(tenant_conn_key, 1)
                redis_client.decr(user_conn_key, 1)
                return False, "Túl sok párhuzamos websocket kapcsolat tenant szinten.", None
            if user_count > ws_max_connections_per_user():
                redis_client.decr(tenant_conn_key, 1)
                redis_client.decr(user_conn_key, 1)
                return False, "Túl sok párhuzamos websocket kapcsolat felhasználói szinten.", None
            return True, "", {"backend": "redis", "tenant_conn_key": tenant_conn_key, "user_conn_key": user_conn_key}
        except Exception:
            pass
    with ws_connections_lock:
        tenant_count = int(ws_connection_counts.get(tenant_conn_key, 0))
        user_count = int(ws_connection_counts.get(user_conn_key, 0))
        if tenant_count >= ws_max_connections_per_tenant():
            return False, "Túl sok párhuzamos websocket kapcsolat tenant szinten.", None
        if user_count >= ws_max_connections_per_user():
            return False, "Túl sok párhuzamos websocket kapcsolat felhasználói szinten.", None
        ws_connection_counts[tenant_conn_key] = tenant_count + 1
        ws_connection_counts[user_conn_key] = user_count + 1
    return True, "", {"backend": "memory", "tenant_conn_key": tenant_conn_key, "user_conn_key": user_conn_key}


def ws_release_connection(reservation: dict[str, str] | None) -> None:
    if not reservation:
        return
    tenant_conn_key = str(reservation.get("tenant_conn_key") or "").strip()
    user_conn_key = str(reservation.get("user_conn_key") or "").strip()
    if not tenant_conn_key or not user_conn_key:
        return
    if str(reservation.get("backend") or "") == "redis":
        redis_client = get_rate_limit_redis()
        if redis_client is None:
            return
        try:
            redis_client.decr(tenant_conn_key, 1)
            redis_client.decr(user_conn_key, 1)
        except Exception:
            return
        return
    with ws_connections_lock:
        for key in (tenant_conn_key, user_conn_key):
            current = int(ws_connection_counts.get(key, 0))
            if current <= 1:
                ws_connection_counts.pop(key, None)
            else:
                ws_connection_counts[key] = current - 1


__all__ = [
    "ws_allow_message",
    "ws_enabled",
    "ws_idle_timeout_sec",
    "ws_max_message_chars",
    "ws_release_connection",
    "ws_try_acquire_connection",
]
