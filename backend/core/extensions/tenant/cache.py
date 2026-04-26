# Ez a fájl a tenant-kezeléshez kapcsolódó egyik backend építőelemet tartalmazza.
from __future__ import annotations

from core.capabilities.cache import (
    domain2tenant_cache_key,
    get_cache,
    tenant_cache_key,
)


def invalidate_tenant_cache(slug: str | None) -> None:
    """Tenant/security_version/config változás után: tenant snapshot cache törlése."""
    if not slug:
        return
    get_cache().delete(tenant_cache_key(slug))


def invalidate_domain2tenant_cache(host: str | None) -> None:
    """Domain→tenant mapping változás után: domain cache törlése."""
    normalized_host = (host or "").strip().lower()
    if not normalized_host:
        return
    get_cache().delete(domain2tenant_cache_key(normalized_host))


__all__ = ["invalidate_tenant_cache", "invalidate_domain2tenant_cache"]
