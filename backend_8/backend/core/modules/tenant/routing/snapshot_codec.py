# backend/core/modules/tenant/routing/snapshot_codec.py
# Feladat: Tenant snapshot cache szerializációs helper. TenantSnapshot objektumot JSON-kompatibilis adatra és vissza alakít, hogy routing cache-ben stabil formátum legyen. Tenant routing cache codec.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json
from datetime import datetime

from core.modules.tenant.dto import TenantConfig, TenantDomainInfo, TenantSnapshot, TenantStatus


def tenant_to_json(tenant: TenantSnapshot) -> str:
    return json.dumps(
        {
            "id": tenant.tenant_id,
            "slug": tenant.slug,
            "name": tenant.name,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "security_version": tenant.security_version,
            "status": {
                "tenant_id": tenant.status.tenant_id,
                "slug": tenant.status.slug,
                "is_active": tenant.status.is_active,
                "suspended_reason": tenant.status.suspended_reason,
            },
            "config": {
                "tenant_id": tenant.config.tenant_id,
                "slug": tenant.config.slug,
                "package": tenant.config.package,
                "feature_flags": tenant.config.feature_flags,
                "limits": tenant.config.limits,
            },
            "domain": (
                {
                    "request_host": tenant.domain.request_host,
                    "resolved_host": tenant.domain.resolved_host,
                    "is_custom_domain": tenant.domain.is_custom_domain,
                    "verified_at": tenant.domain.verified_at.isoformat() if tenant.domain.verified_at else None,
                }
                if tenant.domain
                else None
            ),
        }
    )


def tenant_from_json(raw: str) -> TenantSnapshot:
    data = json.loads(raw)
    created_at = data.get("created_at")
    if created_at:
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    else:
        from core.kernel.runtime.clock import utc_now

        created_at = utc_now()

    domain_raw = data.get("domain")
    domain = None
    if domain_raw:
        verified_at = domain_raw.get("verified_at")
        domain = TenantDomainInfo(
            request_host=domain_raw.get("request_host"),
            resolved_host=domain_raw.get("resolved_host"),
            is_custom_domain=bool(domain_raw.get("is_custom_domain")),
            verified_at=datetime.fromisoformat(verified_at.replace("Z", "+00:00")) if verified_at else None,
        )

    status_raw = data.get("status") or {}
    config_raw = data.get("config") or {}
    return TenantSnapshot(
        tenant_id=data.get("id"),
        slug=data["slug"],
        name=data["name"],
        created_at=created_at,
        security_version=data.get("security_version", 0),
        status=TenantStatus(
            tenant_id=status_raw.get("tenant_id", data.get("id")),
            slug=status_raw.get("slug", data["slug"]),
            is_active=status_raw.get("is_active", True),
            suspended_reason=status_raw.get("suspended_reason"),
        ),
        config=TenantConfig(
            tenant_id=config_raw.get("tenant_id", data.get("id")),
            slug=config_raw.get("slug", data["slug"]),
            package=config_raw.get("package", "free"),
            feature_flags=config_raw.get("feature_flags") or {},
            limits=config_raw.get("limits") or {},
        ),
        domain=domain,
    )
