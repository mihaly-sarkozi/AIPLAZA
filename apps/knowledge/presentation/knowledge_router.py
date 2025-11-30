from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from apps.core.middleware.rate_limit_middleware import limiter

from apps.knowledge.adapter.http.request import KBCreate, KBUpdate, KBDelete, KBTrainRequest
from apps.knowledge.adapter.http.response import KBOut

from apps.core.security.auth_dependencies import get_current_user_admin
from apps.core.di import get_kb_service
from apps.knowledge.application.knowledge_service import KnowledgeBaseService

router = APIRouter()


@router.get("/kb", response_model=list[KBOut])
def list_kb(
    request: Request,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user=Depends(get_current_user_admin)
):
    return svc.list_all()


@router.post("/kb", response_model=KBOut)
@limiter.limit("5/minute")
def create_kb(
    request: Request,
    data: KBCreate,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user=Depends(get_current_user_admin)
):
    try:
        return svc.create(data.name, data.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/kb/{uuid}", response_model=KBOut)
def update_kb(
    request: Request,
    uuid: str,
    data: KBUpdate,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user=Depends(get_current_user_admin)
):
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
    user=Depends(get_current_user_admin)
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
    svc: KnowledgeBaseService = Depends(get_kb_service)
):
    return await svc.add_block(uuid, data.title, data.content)


# --- TRAIN TEXT (külön endpoint, ha kell) ---
@router.post("/kb/{uuid}/train/text")
async def train_text(
    uuid: str,
    data: KBTrainRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service)
):
    return await svc.add_block(uuid, data.title, data.content)

# --- TRAIN FILE ---
@router.post("/kb/{uuid}/train/file")
async def train_file(
    uuid: str,
    file: UploadFile = File(...),
    svc: KnowledgeBaseService = Depends(get_kb_service)
):
    return await svc.train_from_file(uuid, file)
