from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.kb.kb_indexing.bootstrap.dependencies import (
    get_indexing_diagnostics_service,
    require_kb_admin,
)
from apps.kb.kb_indexing.service.IndexingDiagnosticsService import IndexingDiagnosticsService
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User

router = APIRouter()


@router.get("/{kb_id}/indexing/diagnostics")
async def get_kb_indexing_diagnostics(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    diagnostics: IndexingDiagnosticsService = Depends(get_indexing_diagnostics_service),
    current_user: User = Depends(require_kb_admin),
):
    _ = tenant, current_user
    return diagnostics.for_knowledge_base(kb_id).to_dict()


@router.get("/{kb_id}/training-items/{training_item_id}/indexing/diagnostics")
async def get_training_item_indexing_diagnostics(
    kb_id: str,
    training_item_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    diagnostics: IndexingDiagnosticsService = Depends(get_indexing_diagnostics_service),
    current_user: User = Depends(require_kb_admin),
):
    _ = tenant, current_user
    return diagnostics.for_training_item(kb_id, training_item_id).to_dict()


__all__ = ["router"]
