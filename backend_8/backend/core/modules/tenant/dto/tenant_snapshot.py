# backend/core/modules/tenant/dto/tenant_snapshot.py
# Feladat: A tenant_snapshot tenant DTO adatcontractot definiálja. Tenant állapot, domain, config vagy snapshot adatokat hordoz repositoryk, service-ek és routerek között. Vékony tenant adatmodell réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from core.modules.tenant.dto.tenant_config import TenantConfig
from core.modules.tenant.dto.tenant_domain_info import TenantDomainInfo
from core.modules.tenant.dto.tenant_status import TenantStatus


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
