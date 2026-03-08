from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from apps.core.middleware.rate_limit_middleware import limiter
from apps.core.qdrant.qdrant_wrapper import QdrantUnavailableError
from apps.users.domain.user import User

from apps.knowledge.adapter.http.request import (
    KBCreate,
    KBUpdate,
    KBDelete,
    KBTrainRequest,
    KBPermissionsUpdate,
)
from apps.knowledge.adapter.http.response import KBOut, KBPermissionOut

from apps.core.security.auth_dependencies import get_current_user_admin, get_current_user, get_current_user_owner
from apps.core.di import get_kb_service, set_tenant_context_from_request
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.ports.repositories import KbPermissionItem

router = APIRouter(dependencies=[Depends(set_tenant_context_from_request)])


def _permissions_from_create(data: KBCreate) -> list[KbPermissionItem]:
    if not data.permissions:
        return []
    return [
        (p["user_id"], p.get("permission") or "none")
        for p in data.permissions
        if isinstance(p, dict) and "user_id" in p
    ]


@router.get("/kb", response_model=list[KBOut])
def list_kb(
    request: Request,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """Lista: admin/owner mindent lát; user csak azt, amire use/train joga van. can_train = user taníthatja-e."""
    kbs = svc.list_all(current_user_id=user.id, current_user_role=user.role)
    return [
        KBOut(
            uuid=kb.uuid,
            name=kb.name,
            description=kb.description,
            qdrant_collection_name=kb.qdrant_collection_name,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            can_train=svc.user_can_train(kb.uuid, user.id, user.role),
        )
        for kb in kbs
    ]


@router.post("/kb", response_model=KBOut)
@limiter.limit("5/minute")
def create_kb(
    request: Request,
    data: KBCreate,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user_owner),
):
    try:
        perms = _permissions_from_create(data)
        return svc.create(
            data.name, data.description,
            permissions=perms if perms else None,
            current_user_id=user.id,
        )
    except QdrantUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kb/{uuid}/permissions", response_model=list[KBPermissionOut])
def get_kb_permissions(
    uuid: str,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """Összes felhasználó és jogosultság (use/train/none) ehhez a tudástárhoz. Csak train joggal."""
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to manage this knowledge base")
    items = svc.get_permissions_with_users(uuid)
    return [KBPermissionOut.model_validate(x) for x in items]


@router.put("/kb/{uuid}/permissions")
def set_kb_permissions(
    uuid: str,
    data: KBPermissionsUpdate,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """Jogosultságok beállítása: minden felhasználóhoz use/train/none. Csak train joggal; saját jogot nem lehet none-ra állítani."""
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to manage this knowledge base")
    perms: list[KbPermissionItem] = [(p.user_id, p.permission) for p in data.permissions]
    try:
        svc.set_permissions(uuid, perms, current_user_id=user.id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/kb/{uuid}", response_model=KBOut)
def update_kb(
    request: Request,
    uuid: str,
    data: KBUpdate,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """Név/leírás szerkesztése: csak ha train joga van a tudástárhoz."""
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to edit this knowledge base")
    try:
        return svc.update(uuid, data.name, data.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/kb/{uuid}")
def delete_kb(
    request: Request,
    uuid: str,
    data: KBDelete,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user_owner),
):
    try:
        svc.delete(uuid, data.confirm_name)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- TRAIN TEXT (nyers szöveg) ---
@router.post("/kb/{uuid}/train")
async def train_raw_text(
    uuid: str,
    data: KBTrainRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    return await svc.add_block(uuid, data.title, data.content)


# --- TRAIN TEXT (külön endpoint, ha kell) ---
@router.post("/kb/{uuid}/train/text")
async def train_text(
    uuid: str,
    data: KBTrainRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    return await svc.add_block(uuid, data.title, data.content)

# --- TRAIN FILE ---
@router.post("/kb/{uuid}/train/file")
async def train_file(
    uuid: str,
    file: UploadFile = File(...),
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    return await svc.train_from_file(uuid, file)
