# apps/auth/ports/tenant_repository_interface.py
# INTERFÉSZ – A tenant reprezentálja a cég (host) és az adatbázis(tenant) közötti kapcsolatot
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.auth.domain.tenant import Tenant


class TenantRepositoryInterface(ABC):
    """Tenant lekérdezése slug alapján (Host: acme.teappod.hu → slug=acme)."""
    @abstractmethod
    def get_by_slug(self, slug: str) -> Optional["Tenant"]:
        ...

    @abstractmethod
    def get_by_id(self, tenant_id: int) -> Optional["Tenant"]:
        ...

    @abstractmethod
    def create(self, slug: str, name: str) -> "Tenant":
        ...
