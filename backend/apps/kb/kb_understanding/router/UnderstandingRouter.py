from __future__ import annotations

# backend/apps/kb/kb_understanding/router/UnderstandingRouter.py
# Feladat: Megértési HTTP végpontok — job státusz lekérdezés és újrafuttatás.
# Csak request/response + service hívás; minden endpoint kb.train jogosultsággal.
# Sárközi Mihály - 2026.06.11

from fastapi import APIRouter, Depends, HTTPException, status

from apps.kb.kb_understanding.bootstrap.dependencies import (
    get_retry_understanding_service,
    get_understanding_status_service,
    require_kb_train,
)
from apps.kb.kb_understanding.dto.UnderstandingJobRequest import UnderstandingJobRequest
from apps.kb.kb_understanding.dto.UnderstandingJobResponse import UnderstandingJobResponse
from apps.kb.kb_understanding.dto.UnderstandingStatusResponse import UnderstandingStatusResponse
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.service.RetryUnderstandingService import RetryUnderstandingService
from apps.kb.kb_understanding.service.UnderstandingStatusService import UnderstandingStatusService
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User
from shared.utils.tenant_slug import tenant_slug_or_default

router = APIRouter()


def _coded_error_detail(exc: object, *, fallback_code: str) -> dict[str, object]:
    code = str(getattr(exc, "code", fallback_code) or fallback_code)
    detail: dict[str, object] = {"code": code}
    params = getattr(exc, "params", None)
    if params:
        detail["params"] = params
    return detail


@router.get(
    "/{kb_id}/understanding/items/{item_id}",
    response_model=UnderstandingStatusResponse,
)
async def get_understanding_status(
    kb_id: str,
    item_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    status_service: UnderstandingStatusService = Depends(get_understanding_status_service),
    current_user: User = Depends(require_kb_train),
) -> UnderstandingStatusResponse:
    try:
        return status_service.get_status(knowledge_base_id=kb_id, training_item_id=item_id)
    except UnderstandingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=UnderstandingErrorCode.JOB_NOT_FOUND.value),
        ) from exc


@router.post(
    "/{kb_id}/understanding/items/{item_id}/retry",
    response_model=UnderstandingJobResponse,
)
async def retry_understanding(
    kb_id: str,
    item_id: str,
    body: UnderstandingJobRequest | None = None,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    retry_service: RetryUnderstandingService = Depends(get_retry_understanding_service),
    current_user: User = Depends(require_kb_train),
) -> UnderstandingJobResponse:
    try:
        return retry_service.retry(
            knowledge_base_id=kb_id,
            training_item_id=item_id,
            tenant_slug=tenant_slug_or_default(tenant),
            force=bool(body.force) if body is not None else False,
        )
    except UnderstandingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=UnderstandingErrorCode.JOB_NOT_FOUND.value),
        ) from exc
    except UnderstandingProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_coded_error_detail(
                exc, fallback_code=UnderstandingErrorCode.JOB_NOT_RETRYABLE.value
            ),
        ) from exc


__all__ = ["router"]
