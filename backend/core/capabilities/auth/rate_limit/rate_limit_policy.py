"""Pure rate-limit policy for login attempts.

Responsibility: constants, sliding-window threshold checks, and cache-key
builders.  No Redis, no threading, no I/O – only data and decision logic.
This module is importable without any infrastructure dependency.

The infrastructure adapters (Redis / in-memory storage) live in auth_limits.py.
"""
from __future__ import annotations

# --- Thresholds ---------------------------------------------------------

LOGIN_STEP1_MAX_PER_EMAIL: int = 10
LOGIN_STEP1_WINDOW_SEC: int = 3600   # 1 hour

LOGIN_STEP2_MAX_PER_TOKEN: int = 5
LOGIN_STEP2_WINDOW_SEC: int = 60     # 1 minute


# --- Pure logic ---------------------------------------------------------

def prune_old_timestamps(timestamps: list[float], window_sec: float, now: float) -> list[float]:
    """Return only timestamps that fall within the sliding window."""
    return [t for t in timestamps if now - t < window_sec]


def is_within_limit(current_count: int, max_count: int) -> bool:
    """True when another attempt is still allowed (count < max)."""
    return current_count < max_count


# --- Key builders (pure, no I/O) ----------------------------------------

def email_mem_key(tenant_slug: str | None, email: str) -> str:
    """In-memory storage key for step-1 email attempts."""
    return (tenant_slug or "") + ":" + (email or "").strip().lower()


def pending_mem_key(tenant_slug: str | None, pending_token: str) -> str:
    """In-memory storage key for step-2 pending-token attempts."""
    return (tenant_slug or "") + ":" + (pending_token or "").strip()


def email_redis_key(tenant_slug: str | None, email: str) -> str:
    """Redis sorted-set key for step-1 email attempts."""
    t = (tenant_slug or "").strip()
    e = (email or "").strip().lower()
    return f"rl:login_email:{t}:{e}"


def pending_redis_key(tenant_slug: str | None, pending_token: str) -> str:
    """Redis sorted-set key for step-2 pending-token attempts."""
    t = (tenant_slug or "").strip()
    p = (pending_token or "").strip()
    return f"rl:login_pending:{t}:{p}"


__all__ = [
    "LOGIN_STEP1_MAX_PER_EMAIL",
    "LOGIN_STEP1_WINDOW_SEC",
    "LOGIN_STEP2_MAX_PER_TOKEN",
    "LOGIN_STEP2_WINDOW_SEC",
    "email_mem_key",
    "email_redis_key",
    "is_within_limit",
    "pending_mem_key",
    "pending_redis_key",
    "prune_old_timestamps",
]
