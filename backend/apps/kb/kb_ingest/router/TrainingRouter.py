from __future__ import annotations

# backend/apps/kb/kb_training/router/TrainingRouter.py
# Feladat: Tanítási HTTP végpontok (szöveg batch indítás, batch részletek).
# Sárközi Mihály - 2026.06.07

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from apps.kb.kb_reading.dto.FileEstimateCommand import FileEstimateCommand
from apps.kb.kb_reading.service.EstimateFilesService import EstimateFilesService
from apps.kb.kb_training.bootstrap.dependencies import (
    get_estimate_files_service,
    get_training_batch_service,
    get_training_file_service,
    get_training_text_service,
    require_kb_train,
)
from apps.kb.kb_training.dto.TrainingBatchStatusResponse import TrainingBatchStatusResponse
from apps.kb.kb_training.dto.TrainingFileEstimateResponse import TrainingFileEstimateResponse
from apps.kb.kb_training.dto.TrainingTextResponse import TrainingTextResponse
from apps.kb.kb_training.mapper.training_file_estimate_mapper import to_training_file_estimate
from apps.kb.kb_training.mapper.training_response_mapper import to_text_response, to_text_response_from_batch_status
from apps.kb.kb_training.dto.TrainingTextRequest import TrainingTextRequest
from apps.kb.kb_training.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_training.errors.TrainingDuplicateError import TrainingDuplicateError
from apps.kb.kb_training.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_training.errors.TrainingProcessingError import TrainingProcessingError
from apps.kb.kb_training.errors.TrainingQueueUnavailableError import TrainingQueueUnavailableError
from apps.kb.kb_training.service.TrainingBatchService import TrainingBatchService
from apps.kb.kb_training.service.TrainingFileService import TrainingFileService
from apps.kb.kb_training.service.TrainingTextService import TrainingTextService
from apps.kb.kb_training.validation.TrainingValidationError import TrainingValidationError
from apps.kb.shared.errors import KbNotFoundError, KbValidationError
from shared.utils.tenant_slug import tenant_slug_or_default
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User

router = APIRouter()


def _coded_error_detail(exc: object, *, fallback_code: str) -> dict[str, object]:
    code = str(getattr(exc, "code", fallback_code) or fallback_code)
    detail: dict[str, object] = {"code": code}
    params = getattr(exc, "params", None)
    if params:
        detail["params"] = params
    return detail


@router.post("/{kb_id}/training/text", response_model=TrainingTextResponse)
async def create_text_training_batch(
    kb_id: str,
    body: TrainingTextRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    training_service: TrainingTextService = Depends(get_training_text_service),
    current_user: User = Depends(require_kb_train),
) -> TrainingTextResponse:
    try:
        result = await training_service.submit_text_training(
            tenant=tenant_slug_or_default(tenant),
            knowledge_base_id=kb_id,
            created_by=current_user.id,
            request=body,
        )
        return to_text_response(
            batch_id=result.training_batch_id,
            status=result.status,
            created_at=result.created_at,
            completed_at=result.completed_at,
        )
    except TrainingDuplicateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.DUPLICATE_CONTENT.value),
        ) from exc
    except TrainingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
        ) from exc
    except TrainingQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.QUEUE_UNAVAILABLE.value),
        ) from exc
    except TrainingProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.INTERNAL_ERROR.value),
        ) from exc
    except KbValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
        ) from exc


@router.post("/{kb_id}/training/files/estimate", response_model=TrainingFileEstimateResponse)
async def estimate_file_training(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    estimate_service: EstimateFilesService = Depends(get_estimate_files_service),
    files: list[UploadFile] = File(...),
    _: User = Depends(require_kb_train),
) -> TrainingFileEstimateResponse:
    _ = kb_id
    result = await estimate_service.execute(FileEstimateCommand(tenant=tenant, uploads=files))
    return to_training_file_estimate(result)


@router.post("/{kb_id}/training/files", response_model=TrainingTextResponse)
async def create_file_training_batch(
    kb_id: str,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    file_service: TrainingFileService = Depends(get_training_file_service),
    batch_service: TrainingBatchService = Depends(get_training_batch_service),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_kb_train),
) -> TrainingTextResponse:
    try:
        result = await file_service.submit_file_training(
            tenant=tenant_slug_or_default(tenant),
            knowledge_base_id=kb_id,
            created_by=current_user.id,
            uploads=files,
        )
        return to_text_response_from_batch_status(batch_service.get_status(result.training_batch_id))
    except TrainingDuplicateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.DUPLICATE_CONTENT.value),
        ) from exc
    except TrainingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
        ) from exc
    except TrainingQueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.QUEUE_UNAVAILABLE.value),
        ) from exc
    except TrainingProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.INTERNAL_ERROR.value),
        ) from exc
    except KbValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.VALIDATION_ERROR.value),
        ) from exc


@router.get("/training/batches/{batch_id}", response_model=TrainingBatchStatusResponse)
def get_training_batch(
    batch_id: str,
    batch_service: TrainingBatchService = Depends(get_training_batch_service),
    _: User = Depends(require_kb_train),
) -> TrainingBatchStatusResponse:
    try:
        return batch_service.get_status(batch_id)
    except TrainingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.BATCH_NOT_FOUND.value),
        ) from exc
    except KbNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_coded_error_detail(exc, fallback_code=TrainingErrorCode.BATCH_NOT_FOUND.value),
        ) from exc


__all__ = ["router"]
