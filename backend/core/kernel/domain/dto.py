# backend/core/kernel/domain/dto.py
# Feladat: A custom domain HTTP API request és response DTO-it definiálja. Tartalmaz domain létrehozási/verifikációs requesteket, domain rekord választ DNS challenge mezőkkel, valamint tenant domain overview választ. Kernel domain DTO réteg a service és router között.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel

from core.modules.tenant.dto import TenantDomain


class DomainCreateRequest(BaseModel):
    domain: str


class DomainVerifyRequest(BaseModel):
    domain: str


class DomainRecordResponse(BaseModel):
    domain: str
    state: str = "custom_pending"
    verified_at: str | None = None
    is_primary: bool = False
    cname_target: str | None = None
    dns_record_type: str | None = None
    dns_record_name: str | None = None
    dns_record_value: str | None = None

    @classmethod
    def from_domain(cls, domain: TenantDomain, *, is_primary: bool = False) -> "DomainRecordResponse":
        return cls(
            domain=domain.domain,
            state="platform_primary" if is_primary else ("custom_verified" if domain.verified_at else "custom_pending"),
            verified_at=domain.verified_at.isoformat() if domain.verified_at else None,
            is_primary=is_primary,
        )


class DomainOverviewResponse(BaseModel):
    tenant_slug: str
    primary_domain: DomainRecordResponse
    active_host: str | None = None
    active_custom_domain: bool = False
    custom_domains: tuple[DomainRecordResponse, ...] = ()
