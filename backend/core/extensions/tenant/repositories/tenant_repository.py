from __future__ import annotations

from core.extensions.tenant.repositories.tenant_read_repository import TenantReadRepository
from core.extensions.tenant.repositories.tenant_write_repository import TenantWriteRepository


class TenantRepository(TenantReadRepository, TenantWriteRepository):
    """Compatibility adapter that preserves the existing combined repository API."""


__all__ = ["TenantRepository"]
