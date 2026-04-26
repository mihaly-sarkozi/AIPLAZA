# Ez a fájl az adatátadási objektumokat és a külső interfészhez tartozó struktúrákat tartalmazza.
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from core.extensions.tenant.dto.tenant_config import TenantConfig
from core.extensions.tenant.dto.tenant_domain_info import TenantDomainInfo
from core.extensions.tenant.dto.tenant_status import TenantStatus


@dataclass(frozen=True)
class TenantSnapshot:
    tenant_id: int
    slug: str
    name: str
    created_at: datetime
    security_version: int
    status: TenantStatus
    config: TenantConfig
    domain: TenantDomainInfo | None = None

    # Ez a metódus a(z) is_active logikáját valósítja meg.
    @property
    def is_active(self) -> bool:
        return self.status.is_active

    # Ez a metódus a(z) with_domain logikáját valósítja meg.
    def with_domain(self, domain: TenantDomainInfo) -> "TenantSnapshot":
        return replace(self, domain=domain)
