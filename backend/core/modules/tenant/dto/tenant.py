# backend/core/modules/tenant/dto/tenant.py
# Feladat: A tenant tenant DTO adatcontractot definiálja. Tenant állapot, domain, config vagy snapshot adatokat hordoz repositoryk, service-ek és routerek között. Vékony tenant adatmodell réteg.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Tenant:
    id: Optional[int]
    slug: str
    name: str
    created_at: datetime
    security_version: int = 0  # növeléskor minden régi token (tenant_ver) érvénytelen
