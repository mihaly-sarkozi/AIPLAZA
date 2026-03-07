# apps/core/security/permissions_changed_store.py
# Rövid életű jel: role/is_active változás miatt ki léptettük a usert; refresh 401-nél ezt adjuk vissza.
# Központi cache (Redis vagy memory) – több worker/instance konzisztens.
# 2026.03 - Sárközi Mihály

from __future__ import annotations

from apps.core.cache import (
    get_cache,
    permissions_changed_cache_key,
    PERMISSIONS_CHANGED_TTL_SEC,
)


def set(tenant_slug: str | None, user_id: int) -> None:
    get_cache().set(
        permissions_changed_cache_key(tenant_slug, user_id),
        "1",
        PERMISSIONS_CHANGED_TTL_SEC,
    )


def get(tenant_slug: str | None, user_id: int) -> bool:
    key = permissions_changed_cache_key(tenant_slug, user_id)
    return get_cache().get(key) is not None
