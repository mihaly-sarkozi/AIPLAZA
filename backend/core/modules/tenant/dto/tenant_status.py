# backend/core/modules/tenant/dto/tenant_status.py
# Feladat: A tenant_status tenant DTO adatcontractot definiálja. Tenant állapot, domain, config vagy snapshot adatokat hordoz repositoryk, service-ek és routerek között. Vékony tenant adatmodell réteg.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantStatus:
    """Tenant státusz: aktív-e, opcionális felfüggesztés oka."""
    tenant_id: int
    slug: str
    is_active: bool
    suspended_reason: Optional[str] = None  # pl. "payment_overdue", "abuse"
