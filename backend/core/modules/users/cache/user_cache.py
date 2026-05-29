# backend/core/modules/users/cache/user_cache.py
# Feladat: User cache szerializációs és invalidációs helper réteg. JWT light-path payloadból vagy cache-ből minimális User DTO-t épít, és user/id/token-version kulcsok alapján törli a stale adatokat. Auth-érzékeny users cache adapter.
# Sárközi Mihály - 2026.05.21

"""User cache serialization and cache-invalidation helpers.

Responsibility: convert User domain objects to/from a JSON-serialisable cache
representation, build minimal User objects from JWT payloads (light-path fast
lane), and invalidate the per-tenant/user cache entry.

No HTTP, no ASGI, no token verification – only cache I/O and User DTO mapping.
"""
from __future__ import annotations

import json

from core.infrastructure.cache import USER_TTL_SEC, get_cache, user_cache_key
from core.modules.users.domain.dto import User
from core.kernel.runtime.clock import utc_now


def user_to_cache_json(user: User) -> str:
    """Serialize User to a JSON string safe to store in cache (no password_hash)."""
    return json.dumps({
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "name": getattr(user, "name", None),
        "security_version": getattr(user, "security_version", 0),
        "preferred_locale": getattr(user, "preferred_locale", None),
        "preferred_theme": getattr(user, "preferred_theme", None),
        "credentials_password_set": getattr(user, "credentials_password_set", True),
        "pending_email": getattr(user, "pending_email", None),
        "pending_email_expires_at": getattr(user, "pending_email_expires_at", None).isoformat() if getattr(user, "pending_email_expires_at", None) else None,
    })


def user_from_cache_json(s: str) -> User | None:
    """Deserialize a cached JSON string back to a User; returns None on error."""
    try:
        d = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
    return User(
        id=d.get("id"),
        email=d.get("email", ""),
        password_hash="",
        is_active=bool(d.get("is_active", True)),
        role=d.get("role", "user"),
        created_at=utc_now(),
        name=d.get("name"),
        registration_completed_at=None,
        failed_login_attempts=0,
        preferred_locale=d.get("preferred_locale"),
        preferred_theme=d.get("preferred_theme"),
        security_version=d.get("security_version", 0),
        credentials_password_set=bool(d.get("credentials_password_set", True)),
        pending_email=d.get("pending_email"),
    )


def minimal_user_from_payload(payload: dict, user_id: int) -> User:
    """Build a minimal User from a JWT payload (light-path: no DB/cache lookup)."""
    return User(
        id=user_id,
        email="",
        password_hash="",
        is_active=True,
        role=payload.get("role", "user"),
        created_at=utc_now(),
        name=None,
        registration_completed_at=None,
        failed_login_attempts=0,
        preferred_locale=None,
        preferred_theme=None,
        security_version=payload.get("user_ver", 0),
    )


def invalidate_user_cache(tenant_slug: str | None, user_id: int) -> None:
    """Remove a user's cache entry after role change, deactivation, etc."""
    get_cache().delete(user_cache_key(tenant_slug, user_id))


def get_cached_user(tenant_slug: str | None, user_id: int) -> User | None:
    """Return a cached User or None (does not fall back to the database)."""
    cache = get_cache()
    raw = cache.get(user_cache_key(tenant_slug, user_id))
    if not raw:
        return None
    user = user_from_cache_json(raw)
    if user and getattr(user, "is_active", True):
        return user
    cache.delete(user_cache_key(tenant_slug, user_id))
    return None


def set_cached_user(tenant_slug: str | None, user: User) -> None:
    """Store a User in the cache."""
    get_cache().set(user_cache_key(tenant_slug, user.id), user_to_cache_json(user), USER_TTL_SEC)


__all__ = [
    "get_cached_user",
    "invalidate_user_cache",
    "minimal_user_from_payload",
    "set_cached_user",
    "user_from_cache_json",
    "user_to_cache_json",
]
