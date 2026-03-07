# apps/core/rate_limit/auth_limits.py
# Célzott limitek: login step1 per email (10/óra), login step2 per pending_token (5/perc).
# REDIS_URL beállítva → Redis (központi, tenant dimenzióval); különben in-memory (dev).
# 2026.03 - Sárközi Mihály

import threading
import time
from collections import defaultdict

from apps.core.redis_client import get_redis

# In-memory fallback (ha nincs redis_url)
_email_attempts: dict[str, list[float]] = defaultdict(list)
_email_lock = threading.Lock()
_pending_attempts: dict[str, list[float]] = defaultdict(list)
_pending_lock = threading.Lock()

LOGIN_STEP1_MAX_PER_EMAIL = 10
LOGIN_STEP1_WINDOW_SEC = 3600  # 1 óra
LOGIN_STEP2_MAX_PER_TOKEN = 5
LOGIN_STEP2_WINDOW_SEC = 60    # 1 perc


def _prune(attempts: list[float], window_sec: float, now: float) -> list[float]:
    return [t for t in attempts if now - t < window_sec]


def _redis_key_email(tenant_slug: str | None, email: str) -> str:
    t = (tenant_slug or "").strip()
    e = (email or "").strip().lower()
    return f"rl:login_email:{t}:{e}"


def _redis_key_pending(tenant_slug: str | None, pending_token: str) -> str:
    t = (tenant_slug or "").strip()
    p = (pending_token or "").strip()
    return f"rl:login_pending:{t}:{p}"


def check_login_step1_email(email: str, tenant_slug: str | None = None) -> bool:
    """
    Login step1: max 10 kísérlet / óra / email (tenant szerint).
    Vissza: True = engedélyezve, False = limit túllépve (429).
    Redis: sorted set, sliding window; in-memory fallback ha nincs Redis.
    """
    if not (email and email.strip()):
        return True
    key = email.strip().lower()
    r = get_redis()
    if r is not None:
        now = time.time()
        redis_key = _redis_key_email(tenant_slug, email)
        r.zremrangebyscore(redis_key, "-inf", now - LOGIN_STEP1_WINDOW_SEC)
        n = r.zcard(redis_key)
        if n >= LOGIN_STEP1_MAX_PER_EMAIL:
            return False
        r.zadd(redis_key, {f"{now}:{n}": now})
        r.expire(redis_key, LOGIN_STEP1_WINDOW_SEC + 60)
        return True
    now = time.monotonic()
    with _email_lock:
        mem_key = (tenant_slug or "") + ":" + key
        _email_attempts[mem_key] = _prune(_email_attempts[mem_key], LOGIN_STEP1_WINDOW_SEC, now)
        if len(_email_attempts[mem_key]) >= LOGIN_STEP1_MAX_PER_EMAIL:
            return False
        _email_attempts[mem_key].append(now)
    return True


def check_login_step2_pending_token(pending_token: str, tenant_slug: str | None = None) -> bool:
    """
    Login step2: max 5 kísérlet / perc / pending_token (tenant szerint).
    Vissza: True = engedélyezve, False = limit túllépve (429).
    Redis: sorted set, sliding window; in-memory fallback ha nincs Redis.
    """
    if not (pending_token and pending_token.strip()):
        return True
    key = pending_token.strip()
    r = get_redis()
    if r is not None:
        now = time.time()
        redis_key = _redis_key_pending(tenant_slug, pending_token)
        r.zremrangebyscore(redis_key, "-inf", now - LOGIN_STEP2_WINDOW_SEC)
        n = r.zcard(redis_key)
        if n >= LOGIN_STEP2_MAX_PER_TOKEN:
            return False
        r.zadd(redis_key, {f"{now}:{n}": now})
        r.expire(redis_key, LOGIN_STEP2_WINDOW_SEC + 60)
        return True
    now = time.monotonic()
    with _pending_lock:
        mem_key = (tenant_slug or "") + ":" + key
        _pending_attempts[mem_key] = _prune(_pending_attempts[mem_key], LOGIN_STEP2_WINDOW_SEC, now)
        if len(_pending_attempts[mem_key]) >= LOGIN_STEP2_MAX_PER_TOKEN:
            return False
        _pending_attempts[mem_key].append(now)
    return True
