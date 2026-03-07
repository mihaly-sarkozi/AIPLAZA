# apps/auth/domain/tenant_status.py
# Tenant állapot (aktív/felfüggesztett) – cache és szűréshez.
# 2026.03 – Sárközi Mihály

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TenantStatus:
    """Tenant státusz: aktív-e, opcionális felfüggesztés oka."""
    tenant_id: int
    slug: str
    is_active: bool
    suspended_reason: Optional[str] = None  # pl. "payment_overdue", "abuse"
