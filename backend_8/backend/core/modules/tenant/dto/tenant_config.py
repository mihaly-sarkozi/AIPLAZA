# backend/core/modules/tenant/dto/tenant_config.py
# Feladat: A tenant_config tenant DTO adatcontractot definiálja. Tenant állapot, domain, config vagy snapshot adatokat hordoz repositoryk, service-ek és routerek között. Vékony tenant adatmodell réteg.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: int # Tenant azonosító
    slug: str # tenant slug(subdomain név)
    package: str  # pl. "free", "pro", "enterprise"
    feature_flags: dict[str, bool]  # pl. {"sso": True, "api_export": False}
    limits: dict[str, Any]  # pl. {"max_users": 10, "storage_mb": 1024}
