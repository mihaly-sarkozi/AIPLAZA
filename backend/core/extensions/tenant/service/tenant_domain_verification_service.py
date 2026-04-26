# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
from __future__ import annotations

from core.kernel.clock import utc_now
from core.extensions.tenant.ports import TenantWriteRepositoryPort


class TenantDomainVerificationService:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, tenant_repository: TenantWriteRepositoryPort) -> None:
        self.tenant_repo = tenant_repository

    # Ez a metódus a(z) verify_domain logikáját valósítja meg.
    def verify_domain(self, domain: str, *, actor_user_id: int | None = None):
        return self.tenant_repo.verify_domain(
            domain,
            verified_at=utc_now(),
            updated_by=actor_user_id,
        )


__all__ = ["TenantDomainVerificationService"]
