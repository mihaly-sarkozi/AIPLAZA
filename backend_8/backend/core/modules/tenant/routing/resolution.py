# backend/core/modules/tenant/routing/resolution.py
# Feladat: Host/domain alapú tenant feloldási szolgáltatás. Cache-ből és tenant read repositoryból tenant snapshotot keres, normalizálja a hostot, és eldönti a custom/platform domain kontextust. Tenant routing service.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json

from core.infrastructure.cache import (
    DOMAIN2TENANT_TTL_SEC,
    TENANT_TTL_SEC,
    domain2tenant_cache_key,
    get_cache,
    tenant_cache_key,
)
from core.modules.tenant.routing.snapshot_codec import tenant_from_json, tenant_to_json
from core.modules.tenant.ports import TenantReadRepositoryPort


class TenantResolutionService:
    def __init__(self, *, tenant_repo: TenantReadRepositoryPort, routing_policy) -> None:
        self._tenant_repo = tenant_repo
        self._routing_policy = routing_policy

    def warm_tenant_cache(self, slug: str) -> None:
        tenant = self._tenant_repo.get_snapshot_by_slug(slug)
        if tenant:
            get_cache().set(tenant_cache_key(slug), tenant_to_json(tenant), TENANT_TTL_SEC)

    def _get_slug_for_host(self, host: str) -> tuple[str | None, bool]:
        cache = get_cache()
        key = domain2tenant_cache_key(host)
        cached = cache.get(key)
        if cached is not None:
            if cached == "":
                return None, False
            is_platform_host = self._routing_policy.host_kind(host) in {"platform_root", "platform_subdomain", "localhost"}
            return cached, not is_platform_host

        slug = self._routing_policy.resolve_platform_slug(host)
        is_custom_domain = self._routing_policy.host_kind(host) == "custom_domain"
        if slug is None:
            tenant = self._tenant_repo.get_by_domain(host)
            slug = tenant.slug if tenant else None
            is_custom_domain = tenant is not None
        cache.set(key, slug or "", DOMAIN2TENANT_TTL_SEC)
        return slug, is_custom_domain

    def _get_tenant_snapshot(self, slug: str):
        cache = get_cache()
        key = tenant_cache_key(slug)
        cached = cache.get(key)
        if cached:
            try:
                return tenant_from_json(cached)
            except (json.JSONDecodeError, KeyError, TypeError):
                cache.delete(key)
        tenant = self._tenant_repo.get_snapshot_by_slug(slug)
        if tenant:
            cache.set(key, tenant_to_json(tenant), TENANT_TTL_SEC)
        return tenant

    def get_snapshot(self, slug: str):
        return self._get_tenant_snapshot(slug)

    def resolve_request(self, host: str):
        slug, is_custom_domain = self._get_slug_for_host(host)
        if not slug:
            return None, is_custom_domain, None
        snapshot = self._get_tenant_snapshot(slug)
        return slug, is_custom_domain, snapshot


def warm_tenant_cache(slug: str, tenant_repo: TenantReadRepositoryPort) -> None:
    tenant = tenant_repo.get_snapshot_by_slug(slug)
    if tenant:
        get_cache().set(tenant_cache_key(slug), tenant_to_json(tenant), TENANT_TTL_SEC)
