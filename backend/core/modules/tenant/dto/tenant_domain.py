# backend/core/modules/tenant/dto/tenant_domain.py
# Feladat: A tenant_domain tenant DTO adatcontractot definiálja. Tenant állapot, domain, config vagy snapshot adatokat hordoz repositoryk, service-ek és routerek között. Vékony tenant adatmodell réteg.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TenantDomain:
    """Egy domain (host) hozzárendelése egy tenanthoz; verified_at = ellenőrzött (pl. DNS)."""
    id: Optional[int]
    tenant_id: int
    domain: str  # normalizált: kisbetű, port nélkül
    verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
