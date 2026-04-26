# Infrastruktúra adapter: login rate limiting Redis / in-memory háttérrel.
# Pure policy (konstansok, ablak logika, kulcsépítők) → rate_limit_policy.py
# 2026.03 - Sárközi Mihály

import logging
import threading
import time
from collections import defaultdict

from core.capabilities.auth.rate_limit.rate_limit_policy import (
    LOGIN_STEP1_MAX_PER_EMAIL,
    LOGIN_STEP1_WINDOW_SEC,
    LOGIN_STEP2_MAX_PER_TOKEN,
    LOGIN_STEP2_WINDOW_SEC,
    email_mem_key,
    email_redis_key,
    is_within_limit,
    pending_mem_key,
    pending_redis_key,
    prune_old_timestamps,
)
from core.capabilities.cache.redis_client import get_redis

_log = logging.getLogger(__name__)

# In-memory fallback (ha nincs redis_url)
_email_attempts: dict[str, list[float]] = defaultdict(list)
_email_lock = threading.Lock()
_pending_attempts: dict[str, list[float]] = defaultdict(list)
_pending_lock = threading.Lock()


def check_login_step1_email(email: str, tenant_slug: str | None = None) -> bool:
    """
    Login step1: max LOGIN_STEP1_MAX_PER_EMAIL kísérlet / óra / email.
    True = engedélyezve, False = limit túllépve (429).
    Redis: sorted set, sliding window; in-memory fallback ha nincs Redis.
    """
    if not (email and email.strip()):
        return True
    r = get_redis()
    if r is not None:
        try:
            now = time.time()
            redis_key = email_redis_key(tenant_slug, email)
            r.zremrangebyscore(redis_key, "-inf", now - LOGIN_STEP1_WINDOW_SEC)
            n = r.zcard(redis_key)
            if not is_within_limit(n, LOGIN_STEP1_MAX_PER_EMAIL):
                return False
            r.zadd(redis_key, {f"{now}:{n}": now})
            r.expire(redis_key, LOGIN_STEP1_WINDOW_SEC + 60)
            return True
        except Exception as e:
            _log.warning("login rate limit (step1 email): Redis failed, using in-memory: %s", e)
    now = time.monotonic()
    with _email_lock:
        mem_key = email_mem_key(tenant_slug, email)
        _email_attempts[mem_key] = prune_old_timestamps(_email_attempts[mem_key], LOGIN_STEP1_WINDOW_SEC, now)
        if not is_within_limit(len(_email_attempts[mem_key]), LOGIN_STEP1_MAX_PER_EMAIL):
            return False
        _email_attempts[mem_key].append(now)
    return True


def check_login_step2_pending_token(pending_token: str, tenant_slug: str | None = None) -> bool:
    """
    Login step2: max LOGIN_STEP2_MAX_PER_TOKEN kísérlet / perc / pending_token.
    True = engedélyezve, False = limit túllépve (429).
    Redis: sorted set, sliding window; in-memory fallback ha nincs Redis.
    """
    if not (pending_token and pending_token.strip()):
        return True
    r = get_redis()
    if r is not None:
        try:
            now = time.time()
            redis_key = pending_redis_key(tenant_slug, pending_token)
            r.zremrangebyscore(redis_key, "-inf", now - LOGIN_STEP2_WINDOW_SEC)
            n = r.zcard(redis_key)
            if not is_within_limit(n, LOGIN_STEP2_MAX_PER_TOKEN):
                return False
            r.zadd(redis_key, {f"{now}:{n}": now})
            r.expire(redis_key, LOGIN_STEP2_WINDOW_SEC + 60)
            return True
        except Exception as e:
            _log.warning("login rate limit (step2 pending): Redis failed, using in-memory: %s", e)
    now = time.monotonic()
    with _pending_lock:
        mem_key = pending_mem_key(tenant_slug, pending_token)
        _pending_attempts[mem_key] = prune_old_timestamps(_pending_attempts[mem_key], LOGIN_STEP2_WINDOW_SEC, now)
        if not is_within_limit(len(_pending_attempts[mem_key]), LOGIN_STEP2_MAX_PER_TOKEN):
            return False
        _pending_attempts[mem_key].append(now)
    return True
