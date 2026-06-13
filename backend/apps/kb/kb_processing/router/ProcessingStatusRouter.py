from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apps.kb.kb_processing.bootstrap.dependencies import get_processing_status_service, require_kb_read
from apps.kb.kb_processing.dto.ProcessingListResponses import ProcessingEventsPage, ProcessingIssuesPage
from apps.kb.kb_processing.dto.ProcessingMetricsResponse import ProcessingMetricsResponse
from apps.kb.kb_processing.service.ProcessingStatusService import ProcessingStatusService
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User

router = APIRouter()


@router.get(
    "/{kb_id}/processing/metrics",
    response_model=ProcessingMetricsResponse,
)
async def get_processing_metrics(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    status_service: ProcessingStatusService = Depends(get_processing_status_service),
    current_user: User = Depends(require_kb_read),
) -> ProcessingMetricsResponse:
    metrics = status_service.get_metrics(kb_id)
    if metrics is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "metrics_not_found"})
    return metrics


@router.get(
    "/{kb_id}/processing/events",
    response_model=ProcessingEventsPage,
)
async def list_processing_events(
    kb_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: RequestTenantContext = Depends(require_tenant_context),
    status_service: ProcessingStatusService = Depends(get_processing_status_service),
    current_user: User = Depends(require_kb_read),
) -> ProcessingEventsPage:
    return status_service.list_events(kb_id, limit=limit, offset=offset)


@router.get(
    "/{kb_id}/processing/issues",
    response_model=ProcessingIssuesPage,
)
async def list_processing_issues(
    kb_id: str,
    issue_status: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: RequestTenantContext = Depends(require_tenant_context),
    status_service: ProcessingStatusService = Depends(get_processing_status_service),
    current_user: User = Depends(require_kb_read),
) -> ProcessingIssuesPage:
    return status_service.list_issues(
        kb_id,
        status=issue_status,
        severity=severity,
        limit=limit,
        offset=offset,
    )


__all__ = ["router"]
