from __future__ import annotations

from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.platform.brand.ports import BrandRepositoryPort
from core.platform.brand.dto import BrandResponse, BrandUpdateRequest
from core.platform.brand.policies import BrandPolicy


class BrandService:
    def __init__(self, repo: BrandRepositoryPort, policy: BrandPolicy | None = None, audit_service=None):
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
