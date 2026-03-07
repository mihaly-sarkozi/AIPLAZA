# apps/auth/ports/tenant_repository_interface.py
# INTERFÉSZ – Tenant, domain→tenant, status, config (cache + DB hibridhez).
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.auth.domain.tenant import Tenant
    from apps.auth.domain.tenant_status import TenantStatus
    from apps.auth.domain.tenant_config import TenantConfig
    from apps.auth.domain.tenant_domain import TenantDomain


class TenantRepositoryInterface(ABC):
    """Tenant lekérdezése slug/domain alapján; status és config cache forrás."""

    @abstractmethod
    def get_by_slug(self, slug: str) -> Optional["Tenant"]:
        ...

    @abstractmethod
    def get_by_id(self, tenant_id: int) -> Optional["Tenant"]:
        ...

    @abstractmethod
    def create(self, slug: str, name: str) -> "Tenant":
        ...

    @abstractmethod
    def get_by_domain(self, domain: str) -> Optional["Tenant"]:
        """Egyedi domain (tenant_domains) vagy subdomain policy nélküli host → tenant. domain normalizált (kisbetű)."""
        ...

    @abstractmethod
    def get_tenant_status(self, slug: str) -> Optional["TenantStatus"]:
        """Tenant status cache forrás (is_active, stb.)."""
        ...

    @abstractmethod
    def get_tenant_config(self, slug: str) -> Optional["TenantConfig"]:
        """Tenant config cache forrás (package, feature_flags, limits)."""
        ...

    @abstractmethod
    def list_domains_for_tenant(self, tenant_id: int) -> list["TenantDomain"]:
        """Nyilvános nyilvántartás: mely domainek tartoznak a tenanthoz (regisztráció/ellenőrzés)."""
        ...
