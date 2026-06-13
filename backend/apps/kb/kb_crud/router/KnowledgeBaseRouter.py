# backend/apps/kb/kb_crud/router/KnowledgeBaseRouter.py
# Feladat: Tudástár CRUD és jogosultság HTTP végpontok.
# Sárközi Mihály - 2026.06.07

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.kb.kb_crud.bootstrap.dependencies import (
    get_create_knowledge_base_service,
    get_delete_knowledge_base_service,
    get_get_knowledge_base_service,
    get_kb_permissions_batch_service,
    get_kb_permissions_service,
    get_list_knowledge_bases_service,
    get_set_kb_permissions_service,
    get_update_knowledge_base_service,
)
from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.dto.BatchPermissionsRequest import BatchPermissionsRequest
from apps.kb.kb_crud.dto.CreateKnowledgeBaseRequest import CreateKnowledgeBaseRequest
from apps.kb.kb_crud.dto.DeleteKnowledgeBaseRequest import DeleteKnowledgeBaseRequest
from apps.kb.kb_crud.dto.KbPermissionResponse import KbPermissionResponse
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.dto.SetPermissionsRequest import SetPermissionsRequest
from apps.kb.kb_crud.dto.UpdateKnowledgeBaseRequest import UpdateKnowledgeBaseRequest
from apps.kb.kb_crud.errors.CrudLimitError import CrudLimitError
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.service.CreateKnowledgeBaseService import CreateKnowledgeBaseService
from apps.kb.kb_crud.service.DeleteKnowledgeBaseService import DeleteKnowledgeBaseService
from apps.kb.kb_crud.service.GetKnowledgeBasePermissionsService import GetKnowledgeBasePermissionsService
from apps.kb.kb_crud.service.GetKnowledgeBaseService import GetKnowledgeBaseService
from apps.kb.kb_crud.service.GetPermissionsBatchService import GetPermissionsBatchService
from apps.kb.kb_crud.service.ListKnowledgeBasesService import ListKnowledgeBasesService
from apps.kb.kb_crud.service.SetKnowledgeBasePermissionsService import SetKnowledgeBasePermissionsService
from apps.kb.kb_crud.service.UpdateKnowledgeBaseService import UpdateKnowledgeBaseService
from apps.kb.shared.errors import KbNotFoundError, KbValidationError
from core.kernel.http.responses import OperationStatusResponse
from core.kernel.http.security_errors import security_http_exception
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.users.domain.dto import User

router = APIRouter(prefix="/kb", tags=["kb"])


def _request_ip(request: Request) -> str | None:
    return getattr(request.client, "host", None) if request.client else None


def _validation_detail(exc: CrudValidationError) -> dict[str, object]:
    return {"code": exc.code}


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_kb(
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: ListKnowledgeBasesService = Depends(get_list_knowledge_bases_service),
    current_user: User = Depends(get_current_user),
) -> list[KnowledgeBaseResponse]:
    """Lista: admin/owner mindent lát; user csak azt, amire use/train joga van."""
    return await service.execute(current_user=current_user)


@router.post("", response_model=KnowledgeBaseResponse)
@limiter.limit("5/minute")
async def create_kb(
    request: Request,
    payload: CreateKnowledgeBaseRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: CreateKnowledgeBaseService = Depends(get_create_knowledge_base_service),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    try:
        return await service.execute(
            payload,
            actor=current_user,
            tenant=tenant,
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except CrudPermissionError as exc:
        raise security_http_exception() from exc
    except CrudLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.reason} if exc.reason else {"code": exc.code},
        ) from exc
    except CrudValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_validation_detail(exc)
        ) from exc
    except KbValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_kb(
    kb_id: str,
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: GetKnowledgeBaseService = Depends(get_get_knowledge_base_service),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    try:
        return await service.execute(kb_id, current_user=current_user)
    except CrudNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}
        ) from exc
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_kb(
    kb_id: str,
    request: Request,
    body: UpdateKnowledgeBaseRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: UpdateKnowledgeBaseService = Depends(get_update_knowledge_base_service),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    """Név/leírás/beállítások szerkesztése: csak train joggal."""
    try:
        return await service.execute(
            kb_id,
            body,
            actor=current_user,
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except CrudPermissionError as exc:
        raise security_http_exception() from exc
    except CrudNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}
        ) from exc
    except CrudValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_validation_detail(exc)
        ) from exc
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except KbValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{kb_id}", response_model=OperationStatusResponse)
async def delete_kb(
    kb_id: str,
    request: Request,
    body: DeleteKnowledgeBaseRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: DeleteKnowledgeBaseService = Depends(get_delete_knowledge_base_service),
    current_user: User = Depends(get_current_user),
) -> OperationStatusResponse:
    try:
        await service.execute(
            kb_id,
            confirm_name=body.confirm_name,
            actor=current_user,
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        return OperationStatusResponse()
    except CrudPermissionError as exc:
        if exc.code == CrudErrorCode.KB_DELETE_NOT_ALLOWED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": exc.code,
                    "message": "Only the tenant owner can delete knowledge bases",
                },
            ) from exc
        raise security_http_exception() from exc
    except CrudNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}
        ) from exc
    except CrudValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_validation_detail(exc)
        ) from exc
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{kb_id}/permissions", response_model=list[KbPermissionResponse])
@limiter.limit("30/minute")
async def get_kb_permissions(
    kb_id: str,
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: GetKnowledgeBasePermissionsService = Depends(get_kb_permissions_service),
    current_user: User = Depends(get_current_user),
) -> list[KbPermissionResponse]:
    """Összes felhasználó és jogosultság (use/train/none) ehhez a tudástárhoz. Csak train joggal."""
    try:
        return await service.execute(kb_id, actor=current_user)
    except CrudPermissionError as exc:
        raise security_http_exception() from exc


@router.post("/permissions/batch", response_model=dict[str, list[KbPermissionResponse]])
@limiter.limit("20/minute")
async def get_kb_permissions_batch(
    request: Request,
    payload: BatchPermissionsRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: GetPermissionsBatchService = Depends(get_kb_permissions_batch_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[KbPermissionResponse]]:
    try:
        return await service.execute(payload.uuids, actor=current_user)
    except CrudPermissionError as exc:
        raise security_http_exception() from exc
    except CrudValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=_validation_detail(exc)
        ) from exc


@router.put("/{kb_id}/permissions", response_model=OperationStatusResponse)
@limiter.limit("60/minute")
async def set_kb_permissions(
    kb_id: str,
    request: Request,
    body: SetPermissionsRequest,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    service: SetKnowledgeBasePermissionsService = Depends(get_set_kb_permissions_service),
    current_user: User = Depends(get_current_user),
) -> OperationStatusResponse:
    """Jogosultságok beállítása. Csak train joggal; a hívó saját jogát nem lehet elvenni."""
    try:
        await service.execute(
            kb_id,
            body.permissions,
            actor=current_user,
            ip=_request_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        return OperationStatusResponse()
    except CrudPermissionError as exc:
        raise security_http_exception() from exc
    except CrudNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}
        ) from exc


__all__ = ["router"]
