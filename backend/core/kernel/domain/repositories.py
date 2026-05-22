# backend/core/kernel/domain/repositories.py
# Feladat: Custom domain repository adapter a tenant repository fölött. Tenant slug alapján tenant snapshotot olvas, tenant domaineket listáz, domain rekordot keres, létrehoz és töröl, miközben a konkrét perzisztencia a tenant modulban marad. Kernel domain repository adapter a DomainService számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.dto import TenantDomain
from core.modules.tenant.ports import TenantRepositoryPort


class DomainRepository:
    def __init__(self, tenant_repository: TenantRepositoryPort):
        self._tenant_repo = tenant_repository

    def get_tenant_by_slug(self, slug: str):
        return self._tenant_repo.get_snapshot_by_slug(slug)

    def list_domains_for_tenant(self, tenant_id: int) -> list[TenantDomain]:
        return self._tenant_repo.list_domains_for_tenant(tenant_id)

    def get_domain(self, domain: str) -> TenantDomain | None:
        return self._tenant_repo.get_domain(domain)

    def create_domain(self, tenant_id: int, domain: str, *, created_by: int | None = None) -> TenantDomain:
        return self._tenant_repo.create_domain(tenant_id, domain, created_by=created_by)

    def delete_domain(self, domain: str, *, tenant_id: int | None = None) -> None:
        self._tenant_repo.delete_domain(domain, tenant_id=tenant_id)
