from __future__ import annotations

# backend/apps/kb/kb_crud/router/KnowledgeBaseRouter.py
# Feladat: Tudástár CRUD HTTP végpontok.
# Sárközi Mihály - 2026.06.07

from fastapi import APIRouter, Depends, HTTPException, status

from apps.kb.kb_crud.bootstrap.dependencies import KnowledgeBaseRepositoryDep
from apps.kb.kb_crud.dto.CreateKnowledgeBaseRequest import CreateKnowledgeBaseRequest
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.dto.UpdateKnowledgeBaseRequest import UpdateKnowledgeBaseRequest
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.service.ArchiveKnowledgeBaseService import ArchiveKnowledgeBaseService
from apps.kb.kb_crud.service.CreateKnowledgeBaseService import CreateKnowledgeBaseService
from apps.kb.kb_crud.service.GetKnowledgeBaseService import GetKnowledgeBaseService
from apps.kb.kb_crud.service.ListKnowledgeBasesService import ListKnowledgeBasesService
from apps.kb.kb_crud.service.UpdateKnowledgeBaseService import UpdateKnowledgeBaseService
from apps.kb.shared.errors import KbNotFoundError, KbValidationError
from core.kernel.http.responses import OperationStatusResponse
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.modules.users.domain.dto import User

router = APIRouter(prefix="/kb", tags=["kb"])


@router.post("/", response_model=KnowledgeBaseResponse)
async def create_kb(
    request: CreateKnowledgeBaseRequest,
    repository: KnowledgeBaseRepositoryDep,
    current_user: User = Depends(require_permission("kb.write")),
) -> KnowledgeBaseResponse:
    try:
        return await CreateKnowledgeBaseService(repository).execute(
            request,
            actor_user_id=current_user.id,
        )
    except CrudValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": exc.code}) from exc
    except KbValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/", response_model=list[KnowledgeBaseResponse])
async def list_kb(
    repository: KnowledgeBaseRepositoryDep,
    _: User = Depends(require_permission("kb.read")),
) -> list[KnowledgeBaseResponse]:
    return await ListKnowledgeBasesService(repository).execute()


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_kb(
    kb_id: str,
    repository: KnowledgeBaseRepositoryDep,
    _: User = Depends(require_permission("kb.read")),
) -> KnowledgeBaseResponse:
    try:
        return await GetKnowledgeBaseService(repository).execute(kb_id)
    except CrudNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}) from exc
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_kb(
    kb_id: str,
    request: UpdateKnowledgeBaseRequest,
    repository: KnowledgeBaseRepositoryDep,
    current_user: User = Depends(require_permission("kb.write")),
) -> KnowledgeBaseResponse:
    try:
        return await UpdateKnowledgeBaseService(repository).execute(
            kb_id,
            request,
            actor_user_id=current_user.id,
        )
    except CrudNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}) from exc
    except CrudValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": exc.code}) from exc
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except KbValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{kb_id}", response_model=OperationStatusResponse)
async def archive_kb(
    kb_id: str,
    repository: KnowledgeBaseRepositoryDep,
    _: User = Depends(require_permission("kb.write")),
) -> OperationStatusResponse:
    try:
        await ArchiveKnowledgeBaseService(repository).execute(kb_id)
        return OperationStatusResponse()
    except CrudNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code}) from exc
    except KbNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
