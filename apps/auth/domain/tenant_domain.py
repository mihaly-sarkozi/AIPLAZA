# apps/auth/domain/tenant_domain.py
# Domain → tenant nyilvántartás: egyedi domainok (pl. app.cegem.hu) és regisztráció/ellenőrzés.
# 2026.03 – Sárközi Mihály

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
