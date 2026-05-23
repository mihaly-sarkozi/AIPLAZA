# backend/apps/chat/application/channel_session_policy.py
# Feladat: Channel chat session cookie és pacing policy helper logikát tartalmaz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import asyncio
import secrets
import threading
from datetime import datetime

from fastapi import Request, Response as MutableResponse

from core.kernel.config.config_loader import settings
from core.kernel.security.cookie_policy import CHANNEL_CHAT_SESSION_COOKIE_NAME, set_channel_chat_session_cookie
from core.kernel.security.rate_limit import get_rate_limit_redis

channel_session_lock = threading.Lock()
channel_session_last_seen_ms: dict[str, int] = {}


def channel_session_limits() -> dict[str, int]:
    return {
        "session_per_minute": max(1, int(getattr(settings, "channel_session_max_per_minute", 30) or 30)),
        "session_burst_10s": max(1, int(getattr(settings, "channel_session_max_burst_10s", 5) or 5)),
        "session_min_interval_ms": max(1, int(getattr(settings, "channel_session_min_interval_ms", 1500) or 1500)),
        "session_wait_max_ms": max(0, int(getattr(settings, "channel_session_wait_max_ms", 900) or 900)),
        "session_cookie_max_age_sec": max(60, int(getattr(settings, "channel_session_cookie_max_age_sec", 86400) or 86400)),
    }


def resolve_or_set_channel_session_id(request: Request, response: MutableResponse) -> str:
    existing = str(request.cookies.get(CHANNEL_CHAT_SESSION_COOKIE_NAME) or "").strip()
    if existing and 12 <= len(existing) <= 200:
        return existing
    session_id = secrets.token_urlsafe(24)
    set_channel_chat_session_cookie(
        response,
        session_id,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
        max_age=channel_session_limits()["session_cookie_max_age_sec"],
    )
    return session_id


async def apply_channel_session_pacing(
    *,
    tenant_id: int,
    credential_id: int,
    session_id: str,
) -> tuple[bool, int, int]:
    limits = channel_session_limits()
    min_interval_ms = int(limits["session_min_interval_ms"])
    wait_max_ms = int(limits["session_wait_max_ms"])
    now_ms = int(datetime.now().timestamp() * 1000)
    wait_applied_ms = 0
    pace_key = f"quota:channel:pace:{tenant_id}:{credential_id}:{session_id}"

    def _retry_after(delta_ms: int) -> int:
        remaining = max(1, min_interval_ms - max(0, delta_ms))
        return max(1, int((remaining + 999) // 1000))

    redis_client = get_rate_limit_redis()
    if redis_client is not None:
        try:
            prev_raw = redis_client.get(pace_key)
            prev_ms = int(prev_raw) if prev_raw is not None else 0
            if prev_ms > 0:
                delta = now_ms - prev_ms
                if delta < min_interval_ms:
                    wait_applied_ms = min(wait_max_ms, max(0, min_interval_ms - delta))
                    if wait_applied_ms > 0:
                        await asyncio.sleep(wait_applied_ms / 1000.0)
                    now_ms = int(datetime.now().timestamp() * 1000)
                    delta = now_ms - prev_ms
                    if delta < min_interval_ms:
                        return False, _retry_after(delta), wait_applied_ms
            redis_client.set(pace_key, str(now_ms), ex=max(5, int((min_interval_ms * 4) / 1000)))
            return True, 0, wait_applied_ms
        except Exception:
            pass

    with channel_session_lock:
        prev_ms = int(channel_session_last_seen_ms.get(pace_key, 0))
    if prev_ms > 0:
        delta = now_ms - prev_ms
        if delta < min_interval_ms:
            wait_applied_ms = min(wait_max_ms, max(0, min_interval_ms - delta))
            if wait_applied_ms > 0:
                await asyncio.sleep(wait_applied_ms / 1000.0)
            now_ms = int(datetime.now().timestamp() * 1000)
            delta = now_ms - prev_ms
            if delta < min_interval_ms:
                return False, _retry_after(delta), wait_applied_ms
    with channel_session_lock:
        channel_session_last_seen_ms[pace_key] = now_ms
    return True, 0, wait_applied_ms


__all__ = [
    "apply_channel_session_pacing",
    "channel_session_last_seen_ms",
    "channel_session_limits",
    "channel_session_lock",
    "resolve_or_set_channel_session_id",
]
