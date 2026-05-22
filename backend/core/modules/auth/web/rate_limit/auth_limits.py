# backend/core/modules/auth/web/rate_limit/auth_limits.py
# Feladat: Login rate limit infrastruktúra adapter Redis és in-memory fallback támogatással. Email alapú step1, pending-token alapú step2, burst és failed-login ban próbálkozásokat mér sliding window kulcsokkal. Auth web security adapter, amely a pure rate_limit_policy döntési logikáját használja.
# Sárközi Mihály - 2026.05.21

import logging
import threading
import time
from collections import defaultdict

from core.modules.auth.web.rate_limit.rate_limit_policy import (
    LOGIN_BURST_MAX_PER_IP_EMAIL_10S,
    LOGIN_BURST_WINDOW_SEC,
    LOGIN_FAILURE_BAN_WINDOW_SEC,
    LOGIN_STEP1_MAX_PER_EMAIL,
    LOGIN_STEP1_WINDOW_SEC,
    LOGIN_STEP2_MAX_PER_TOKEN,
    LOGIN_STEP2_WINDOW_SEC,
    burst_mem_key,
    burst_redis_key,
    email_mem_key,
    email_redis_key,
    failure_ban_mem_key,
    failure_ban_redis_key,
    is_within_limit,
    pending_mem_key,
    pending_redis_key,
    prune_old_timestamps,
)
from core.kernel.config.config_loader import settings
from core.infrastructure.cache.redis_client import get_redis

_log = logging.getLogger(__name__)

# In-memory fallback (ha nincs redis_url)
_email_attempts: dict[str, list[float]] = defaultdict(list)
_email_lock = threading.Lock()
_pending_attempts: dict[str, list[float]] = defaultdict(list)
_pending_lock = threading.Lock()
_burst_attempts: dict[str, list[float]] = defaultdict(list)
_burst_lock = threading.Lock()
_failure_attempts: dict[str, list[float]] = defaultdict(list)
_failure_lock = threading.Lock()


def check_login_step1_email(email: str, tenant_slug: str | None = None) -> bool:
    """
    Login step1: max LOGIN_STEP1_MAX_PER_EMAIL kísérlet / óra / email.
    True = engedélyezve, False = limit túllépve (429).
    Redis: sorted set, sliding window; in-memory fallback ha nincs Redis.
    """
    if not (email and email.strip()):
        return True
    threshold = max(
        1,
        int(getattr(settings, "rate_limit_login_step1_per_email_per_hour", LOGIN_STEP1_MAX_PER_EMAIL) or LOGIN_STEP1_MAX_PER_EMAIL),
    )
    r = get_redis()
    if r is not None:
        try:
            now = time.time()
            redis_key = email_redis_key(tenant_slug, email)
            r.zremrangebyscore(redis_key, "-inf", now - LOGIN_STEP1_WINDOW_SEC)
            n = r.zcard(redis_key)
            if not is_within_limit(n, threshold):
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
        if not is_within_limit(len(_email_attempts[mem_key]), threshold):
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


def check_login_burst(email: str, ip: str | None, tenant_slug: str | None = None) -> bool:
    if not (email and email.strip()):
        return True
    normalized_ip = str(ip or "").strip() or "unknown"
    threshold = max(1, int(getattr(settings, "rate_limit_login_burst_per_10s", LOGIN_BURST_MAX_PER_IP_EMAIL_10S)))
    r = get_redis()
    if r is not None:
        try:
            now = time.time()
            redis_key = burst_redis_key(tenant_slug, email, normalized_ip)
            r.zremrangebyscore(redis_key, "-inf", now - LOGIN_BURST_WINDOW_SEC)
            n = int(r.zcard(redis_key) or 0)
            if not is_within_limit(n, threshold):
                return False
            r.zadd(redis_key, {f"{now}:{n}": now})
            r.expire(redis_key, LOGIN_BURST_WINDOW_SEC + 20)
            return True
        except Exception as e:
            _log.warning("login burst rate limit: Redis failed, using in-memory: %s", e)
    now = time.monotonic()
    with _burst_lock:
        mem_key = burst_mem_key(tenant_slug, email, normalized_ip)
        _burst_attempts[mem_key] = prune_old_timestamps(_burst_attempts[mem_key], LOGIN_BURST_WINDOW_SEC, now)
        if not is_within_limit(len(_burst_attempts[mem_key]), threshold):
            return False
        _burst_attempts[mem_key].append(now)
    return True


def register_failed_login_attempt(email: str, ip: str | None, tenant_slug: str | None = None) -> int:
    if not (email and email.strip()):
        return 0
    normalized_ip = str(ip or "").strip() or "unknown"
    threshold_window = max(60, int(getattr(settings, "rate_limit_login_failure_ban_window_sec", LOGIN_FAILURE_BAN_WINDOW_SEC)))
    r = get_redis()
    if r is not None:
        try:
            now = time.time()
            redis_key = failure_ban_redis_key(tenant_slug, email, normalized_ip)
            r.zremrangebyscore(redis_key, "-inf", now - threshold_window)
            n = int(r.zcard(redis_key) or 0)
            r.zadd(redis_key, {f"{now}:{n}": now})
            r.expire(redis_key, threshold_window + 60)
            return n + 1
        except Exception as e:
            _log.warning("failed login register: Redis failed, using in-memory: %s", e)
    now = time.monotonic()
    with _failure_lock:
        mem_key = failure_ban_mem_key(tenant_slug, email, normalized_ip)
        _failure_attempts[mem_key] = prune_old_timestamps(_failure_attempts[mem_key], threshold_window, now)
        _failure_attempts[mem_key].append(now)
        return len(_failure_attempts[mem_key])
