# backend/core/modules/brand/service/brand_service.py
# Feladat: Tenant brand beállítások application service rétege. A repositoryból olvasott sort BrandResponse-é alakítja, update esetén normalizálja a requestet, perzisztálja az értékeket és audit eseményt ír. Brand service réteg a router és repository között.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import TYPE_CHECKING

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.brand.domain.brand_policy import BrandPolicy
from core.modules.brand.web.requests.brand_update_request import BrandUpdateRequest
from core.modules.brand.web.responses.brand_response import BrandResponse

if TYPE_CHECKING:
    from core.modules.brand.repository.brand_repository import BrandRepository


class BrandService:
    def __init__(self, repo: BrandRepository, policy: BrandPolicy | None = None, audit_service=None):
        self._repo = repo
        self._policy = policy or BrandPolicy()
        self._audit = audit_service

    def get_brand(self) -> BrandResponse:
        row = self._repo.get_settings()
        return self._policy.to_response(row)

    def update_brand(self, body: BrandUpdateRequest, *, updated_by: int | None = None) -> BrandResponse:
        normalized = self._policy.normalize_update(body)
        row = self._repo.upsert_settings(
            **normalized,
            updated_by=updated_by,
        )
        if self._audit:
            self._audit.log(
                AuditLogAction.BRAND_UPDATED,
                user_id=updated_by,
                details=normalized,
            )
        return self._policy.to_response(row)
