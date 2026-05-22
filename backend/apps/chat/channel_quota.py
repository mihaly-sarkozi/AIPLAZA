# backend/apps/chat/channel_quota.py
# Feladat: Channel API kérdéskvóta foglalási és release logikát tartalmaz. Redis alapú napi/perces/session countereket és in-memory fallback countereket kezel, fail-closed production viselkedéssel. Program-specifikus channel quota manager.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from core.kernel.config.config_loader import get_app_env, settings
from core.kernel.config.environment import is_deployed_env
from core.kernel.security.rate_limit import get_rate_limit_redis


def reserve_usage_slot(
    *,
    tenant_id: int,
    credential_id: int,
    daily_limit: int,
    per_minute_limit: int,
    now: datetime,
    period_key: str,
    quota_lock: threading.RLock,
    quota_fallback_counters: dict[str, int],
    session_key: str | None = None,
    session_per_minute_limit: int | None = None,
    session_burst_10s_limit: int | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    minute_key = now.strftime("%Y-%m-%dT%H:%M")
    burst_10s_key = str(int(now.timestamp()) // 10)
    normalized_daily_limit = max(1, int(daily_limit or 1))
    normalized_minute_limit = max(1, int(per_minute_limit or 1))
    session_scope = str(session_key or "").strip() or ""
    normalized_session_per_minute_limit = max(1, int(session_per_minute_limit or 1))
    normalized_session_burst_10s_limit = max(1, int(session_burst_10s_limit or 1))
    session_limit_enabled = bool(session_scope and session_per_minute_limit and session_burst_10s_limit)
    fail_closed = bool(getattr(settings, "channel_quota_fail_closed_without_redis", True))
    try:
        env = get_app_env()
    except Exception:
        env = "dev"

    redis_client = get_rate_limit_redis()
    if redis_client is None and fail_closed and is_deployed_env(env):
        return False, "Channel quota szolgáltatás átmenetileg nem elérhető.", None
    if redis_client is not None:
        day_counter_key = f"quota:channel:day:{tenant_id}:{credential_id}:{period_key}"
        minute_counter_key = f"quota:channel:minute:{tenant_id}:{credential_id}:{minute_key}"
        session_minute_counter_key = (
            f"quota:channel:session:minute:{tenant_id}:{credential_id}:{session_scope}:{minute_key}"
            if session_limit_enabled
            else ""
        )
        session_burst_counter_key = (
            f"quota:channel:session:burst10s:{tenant_id}:{credential_id}:{session_scope}:{burst_10s_key}"
            if session_limit_enabled
            else ""
        )
        try:
            pipe = redis_client.pipeline()
            pipe.incr(day_counter_key, 1)
            pipe.expire(day_counter_key, 3 * 24 * 3600)
            pipe.incr(minute_counter_key, 1)
            pipe.expire(minute_counter_key, 180)
            if session_limit_enabled:
                pipe.incr(session_minute_counter_key, 1)
                pipe.expire(session_minute_counter_key, 180)
                pipe.incr(session_burst_counter_key, 1)
                pipe.expire(session_burst_counter_key, 60)
            results = pipe.execute()
            day_count = int(results[0] or 0)
            minute_count = int(results[2] or 0)
            session_minute_count = int(results[4] or 0) if session_limit_enabled else 0
            session_burst_count = int(results[6] or 0) if session_limit_enabled else 0
            if (
                day_count > normalized_daily_limit
                or minute_count > normalized_minute_limit
                or (
                    session_limit_enabled
                    and (
                        session_minute_count > normalized_session_per_minute_limit
                        or session_burst_count > normalized_session_burst_10s_limit
                    )
                )
            ):
                rollback_pipe = redis_client.pipeline()
                rollback_pipe.decr(day_counter_key, 1)
                rollback_pipe.decr(minute_counter_key, 1)
                if session_limit_enabled:
                    rollback_pipe.decr(session_minute_counter_key, 1)
                    rollback_pipe.decr(session_burst_counter_key, 1)
                rollback_pipe.execute()
                if day_count > normalized_daily_limit:
                    return False, "Napi kérdéslimit elérve.", None
                if minute_count > normalized_minute_limit:
                    return False, "Túl sok kérés rövid idő alatt.", None
                return False, "Túl sok kérés ebből a munkamenetből rövid idő alatt.", None
            return True, "", {
                "backend": "redis",
                "day_counter_key": day_counter_key,
                "minute_counter_key": minute_counter_key,
                "session_minute_counter_key": session_minute_counter_key,
                "session_burst_counter_key": session_burst_counter_key,
            }
        except Exception:
            if fail_closed and is_deployed_env(env):
                return False, "Channel quota szolgáltatás átmenetileg nem elérhető.", None

    day_counter_key = f"quota:channel:day:{tenant_id}:{credential_id}:{period_key}"
    minute_counter_key = f"quota:channel:minute:{tenant_id}:{credential_id}:{minute_key}"
    session_minute_counter_key = (
        f"quota:channel:session:minute:{tenant_id}:{credential_id}:{session_scope}:{minute_key}"
        if session_limit_enabled
        else ""
    )
    session_burst_counter_key = (
        f"quota:channel:session:burst10s:{tenant_id}:{credential_id}:{session_scope}:{burst_10s_key}"
        if session_limit_enabled
        else ""
    )
    with quota_lock:
        day_count = int(quota_fallback_counters.get(day_counter_key, 0)) + 1
        minute_count = int(quota_fallback_counters.get(minute_counter_key, 0)) + 1
        session_minute_count = (
            int(quota_fallback_counters.get(session_minute_counter_key, 0)) + 1
            if session_limit_enabled
            else 0
        )
        session_burst_count = (
            int(quota_fallback_counters.get(session_burst_counter_key, 0)) + 1
            if session_limit_enabled
            else 0
        )
        if day_count > normalized_daily_limit:
            return False, "Napi kérdéslimit elérve.", None
        if minute_count > normalized_minute_limit:
            return False, "Túl sok kérés rövid idő alatt.", None
        if session_limit_enabled and (
            session_minute_count > normalized_session_per_minute_limit
            or session_burst_count > normalized_session_burst_10s_limit
        ):
            return False, "Túl sok kérés ebből a munkamenetből rövid idő alatt.", None
        quota_fallback_counters[day_counter_key] = day_count
        quota_fallback_counters[minute_counter_key] = minute_count
        if session_limit_enabled:
            quota_fallback_counters[session_minute_counter_key] = session_minute_count
            quota_fallback_counters[session_burst_counter_key] = session_burst_count
    return True, "", {
        "backend": "memory",
        "day_counter_key": day_counter_key,
        "minute_counter_key": minute_counter_key,
        "session_minute_counter_key": session_minute_counter_key,
        "session_burst_counter_key": session_burst_counter_key,
    }


def release_usage_slot(
    reservation: dict[str, Any] | None,
    *,
    quota_lock: threading.RLock,
    quota_fallback_counters: dict[str, int],
) -> None:
    if not reservation:
        return
    day_counter_key = str(reservation.get("day_counter_key") or "").strip()
    minute_counter_key = str(reservation.get("minute_counter_key") or "").strip()
    session_minute_counter_key = str(reservation.get("session_minute_counter_key") or "").strip()
    session_burst_counter_key = str(reservation.get("session_burst_counter_key") or "").strip()
    if not day_counter_key or not minute_counter_key:
        return
    backend = str(reservation.get("backend") or "").strip().lower()
    if backend == "redis":
        redis_client = get_rate_limit_redis()
        if redis_client is None:
            return
        try:
            pipe = redis_client.pipeline()
            pipe.decr(day_counter_key, 1)
            pipe.decr(minute_counter_key, 1)
            if session_minute_counter_key:
                pipe.decr(session_minute_counter_key, 1)
            if session_burst_counter_key:
                pipe.decr(session_burst_counter_key, 1)
            pipe.execute()
        except Exception:
            return
        return
    with quota_lock:
        for key in (
            day_counter_key,
            minute_counter_key,
            session_minute_counter_key,
            session_burst_counter_key,
        ):
            if not key:
                continue
            current = int(quota_fallback_counters.get(key, 0))
            if current <= 1:
                quota_fallback_counters.pop(key, None)
            else:
                quota_fallback_counters[key] = current - 1


__all__ = ["release_usage_slot", "reserve_usage_slot"]
