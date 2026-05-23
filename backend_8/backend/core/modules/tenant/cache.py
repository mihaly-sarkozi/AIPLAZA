# backend/core/modules/tenant/cache.py
# Feladat: Tenant routing és tenant snapshot cache invalidációs helper függvényeket tartalmaz. Tenant slug és domain alapú cache kulcsokat töröl, hogy public tenant mutációk után ne maradjon stale routing adat. Tenant-specifikus cache adapter.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.infrastructure.cache import (
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
