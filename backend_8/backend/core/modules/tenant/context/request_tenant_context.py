# backend/core/modules/tenant/context/request_tenant_context.py
# Feladat: A feloldott request tenant adatokat hordozó DTO-t definiálja. Slug, schema, domain, custom-domain flag és tenant snapshot mezők alapján ad egységes contextet middleware, dependency és service rétegeknek. Tenant request contract objektum.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.modules.tenant.dto import TenantConfig, TenantDomainInfo, TenantSnapshot, TenantStatus


@dataclass(frozen=True)
class RequestTenantContext:
    tenant_id: int | None
    slug: str | None
    name: str | None
    created_at: datetime | None
    status: TenantStatus | None
    config: TenantConfig | None
    domain: TenantDomainInfo | None
    correlation_id: str | None
    security_version: int

    @property
    def snapshot(self) -> TenantSnapshot | None:
        if self.tenant_id is None or self.slug is None or self.status is None or self.config is None:
            return None
        from core.kernel.runtime.clock import utc_now

        return TenantSnapshot(
            tenant_id=self.tenant_id,
            slug=self.slug,
            name=self.name or self.slug,
            created_at=self.created_at or utc_now(),
            security_version=self.security_version,
            status=self.status,
            config=self.config,
            domain=self.domain,
        )


def build_request_tenant_context(*, snapshot, request_state) -> RequestTenantContext:
    slug = getattr(snapshot, "slug", None) or getattr(request_state, "tenant_slug", None)
    return RequestTenantContext(
        tenant_id=getattr(snapshot, "tenant_id", None) or getattr(request_state, "tenant_id", None),
        slug=slug,
        name=getattr(snapshot, "name", None),
        created_at=getattr(snapshot, "created_at", None),
        status=getattr(snapshot, "status", None) or getattr(request_state, "tenant_status", None),
        config=getattr(snapshot, "config", None) or getattr(request_state, "tenant_config", None),
        domain=getattr(snapshot, "domain", None) or getattr(request_state, "tenant_domain", None),
        correlation_id=getattr(request_state, "correlation_id", None),
        security_version=getattr(snapshot, "security_version", None) or getattr(request_state, "tenant_security_version", 0) or 0,
    )


def validate_required_tenant_context(tenant: RequestTenantContext) -> tuple[bool, str | None]:
    if not tenant.slug:
        return False, "tenant_required"
    return True, None
