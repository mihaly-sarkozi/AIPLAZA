# backend/core/modules/tenant/dto/tenant_domain_info.py
# Feladat: A tenant_domain_info tenant DTO adatcontractot definiálja. Tenant állapot, domain, config vagy snapshot adatokat hordoz repositoryk, service-ek és routerek között. Vékony tenant adatmodell réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TenantDomainInfo:
    request_host: str | None
    resolved_host: str | None
    is_custom_domain: bool
    verified_at: datetime | None = None
