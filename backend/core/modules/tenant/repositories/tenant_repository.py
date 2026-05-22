# backend/core/modules/tenant/repositories/tenant_repository.py
# Feladat: A tenant read és write repository képességeit egy osztályban összefogó adapter. A service rétegek számára egységes TenantRepository felületet ad, miközben a logika read/write részre bontva marad. Tenant repository façade.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.repositories.tenant_read_repository import TenantReadRepository
from core.modules.tenant.repositories.tenant_write_repository import TenantWriteRepository


class TenantRepository(TenantReadRepository, TenantWriteRepository):
    """Compatibility adapter that preserves the existing combined repository API."""


__all__ = ["TenantRepository"]
