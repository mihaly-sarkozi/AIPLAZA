from __future__ import annotations

from pydantic import BaseModel

from core.extensions.tenant.dto import TenantDomain


class DomainCreateRequest(BaseModel):
    domain: str


class DomainVerifyRequest(BaseModel):
    domain: str


class DomainRecordResponse(BaseModel):
    domain: str
    state: str = "custom_pending"
    verified_at: str | None = None
    is_primary: bool = False

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
