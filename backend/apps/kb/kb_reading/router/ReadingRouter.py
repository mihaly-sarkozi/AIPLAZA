from __future__ import annotations

# backend/apps/kb/kb_reading/router/ReadingRouter.py
# Feladat: Beolvasási végpontok: szöveg, fájl, hálózati cím.
# Sárközi Mihály - 2026.06.07

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from apps.kb.kb_reading.bootstrap.dependencies import (
    get_estimate_files_service,
    get_read_files_service,
    get_read_item_raw_service,
    get_read_run_service,
    require_kb_train,
)
from apps.kb.kb_reading.dto.FileEstimateCommand import FileEstimateCommand
from apps.kb.kb_reading.dto.FileReadCommand import FileReadCommand
from apps.kb.kb_reading.dto.ReadFileEstimateResponse import ReadFileEstimateResponse
from apps.kb.kb_reading.dto.ReadRunDetailResponse import ReadRunDetailResponse
from apps.kb.kb_reading.dto.ReadRunListResponse import ReadRunListResponse
from apps.kb.kb_reading.dto.ReadUrlRequest import ReadUrlRequest
from apps.kb.kb_reading.dto.UrlReadCommand import UrlReadCommand
from apps.kb.kb_reading.service.EstimateFilesService import EstimateFilesService
from apps.kb.kb_reading.service.ReadFilesService import ReadFilesService
from apps.kb.kb_reading.service.ReadItemRawService import ReadItemRawService
from apps.kb.kb_reading.service.ReadRunService import ReadRunService
from apps.kb.kb_reading.service.ReadUrlsService import ReadUrlsService
from apps.kb.kb_reading.service.ReadingResponseMapper import content_disposition_filename
from apps.kb.shared.errors import KbNotFoundError, KbValidationError
from shared.utils.tenant_slug import tenant_slug_or_default
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User

router = APIRouter()


@router.post("/{kb_id}/ingest/files/estimate", response_model=ReadFileEstimateResponse)
async def estimate_file_ingest_run(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    estimate_service: EstimateFilesService = Depends(get_estimate_files_service),
    files: list[UploadFile] = File(...),
    _: User = Depends(require_kb_train),
) -> ReadFileEstimateResponse:
    """Végpont: fájl becslés futtatása."""
    _ = kb_id
    return await estimate_service.execute(
        FileEstimateCommand(tenant=tenant, uploads=files),
    )


@router.post("/{kb_id}/ingest/files", response_model=ReadRunDetailResponse)
async def create_file_ingest_run(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    files_service: ReadFilesService = Depends(get_read_files_service),
    run_service: ReadRunService = Depends(get_read_run_service),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_kb_train),
) -> ReadRunDetailResponse:
    """Végpont: fájl beolvasás indítása."""
    try:
        result = await files_service.execute(
            FileReadCommand(
                tenant=tenant_slug_or_default(tenant),
                knowledge_base_id=kb_id,
                created_by=current_user.id,
                uploads=files,
            ),
        )
        return run_service.get_detail(result.read_run_id)
    except KbValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{kb_id}/ingest/urls", response_model=ReadRunDetailResponse)
async def create_url_ingest_run(
    kb_id: str,
    body: ReadUrlRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    urls_service: ReadUrlsService = Depends(get_read_urls_service),
    run_service: ReadRunService = Depends(get_read_run_service),
    current_user: User = Depends(require_kb_train),
) -> ReadRunDetailResponse:
    """Végpont: hálózati cím beolvasás indítása."""
    try:
        result = await urls_service.execute(
            UrlReadCommand(
                tenant=tenant_slug_or_default(tenant),
                knowledge_base_id=kb_id,
                created_by=current_user.id,
                request=body,
            ),
        )
        return run_service.get_detail(result.read_run_id)
    except KbValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{kb_id}/ingest/runs", response_model=ReadRunListResponse)
def list_ingest_runs(
    kb_id: str,
    run_service: ReadRunService = Depends(get_read_run_service),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_kb_train),
) -> ReadRunListResponse:
    """Végpont: futások listázása."""
    return run_service.list_runs(knowledge_base_id=kb_id, limit=limit, offset=offset)


@router.get("/ingest/runs/{run_id}", response_model=ReadRunDetailResponse)
def get_ingest_run(
    run_id: str,
    run_service: ReadRunService = Depends(get_read_run_service),
    _: User = Depends(require_kb_train),
) -> ReadRunDetailResponse:
    """Végpont: futás részleteinek lekérése."""
    try:
        return run_service.get_detail(run_id)
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/ingest/items/{item_id}/raw")
def get_ingest_item_raw(
    item_id: str,
    raw_service: ReadItemRawService = Depends(get_read_item_raw_service),
    _: User = Depends(require_kb_train),
) -> Response:
    """Végpont: elem nyers tartalmának letöltése."""
    try:
        payload = raw_service.get_raw(item_id)
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(
        content=payload.body,
        media_type=payload.media_type,
        headers={"Content-Disposition": content_disposition_filename(payload.filename)},
    )


__all__ = ["router"]
