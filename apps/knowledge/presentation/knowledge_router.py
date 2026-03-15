import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, Query
from openai import AuthenticationError as OpenAIAuthError, APIError as OpenAIAPIError
from config.settings import settings
from apps.core.middleware.rate_limit_middleware import limiter
from apps.core.qdrant.qdrant_wrapper import QdrantUnavailableError
from apps.users.domain.user import User

from apps.knowledge.adapter.http.request import (
    KBCreate,
    KBUpdate,
    KBDelete,
    KBTrainRequest,
    KBPermissionsUpdate,
    KBBatchPermissionsRequest,
    KBDsarSearchRequest,
    KBDsarDeleteRequest,
)
from apps.knowledge.adapter.http.response import KBOut, KBPermissionOut

from apps.core.security.auth_dependencies import get_current_user_admin, get_current_user, get_current_user_owner
from apps.core.di import get_kb_service, set_tenant_context_from_request, get_audit_service
from apps.knowledge.application.knowledge_service import KnowledgeBaseService
from apps.knowledge.ports.repositories import KbPermissionItem
from apps.knowledge.application.pii_filter import PiiConfirmationRequiredError

router = APIRouter(dependencies=[Depends(set_tenant_context_from_request)])
_ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".xls"}
_ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


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
    trainable_ids = svc.get_trainable_kb_ids(user.id, user.role)
    return [
        KBOut(
            uuid=kb.uuid,
            name=kb.name,
            description=kb.description,
            qdrant_collection_name=kb.qdrant_collection_name,
            personal_data_mode=getattr(kb, "personal_data_mode", None) or "no_personal_data",
            personal_data_sensitivity=getattr(kb, "personal_data_sensitivity", None) or "medium",
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            can_train=bool(kb.id is not None and kb.id in trainable_ids),
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
@limiter.limit("30/minute")
def get_kb_permissions(
    request: Request,
    uuid: str,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """Összes felhasználó és jogosultság (use/train/none) ehhez a tudástárhoz. Csak train joggal."""
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to manage this knowledge base")
    items = svc.get_permissions_with_users(uuid)
    return [KBPermissionOut.model_validate(x) for x in items]


@router.post("/kb/permissions/batch")
@limiter.limit("20/minute")
def get_kb_permissions_batch(
    request: Request,
    data: KBBatchPermissionsRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    unique_uuids: list[str] = []
    seen: set[str] = set()
    for raw in data.uuids:
        kb_uuid = (raw or "").strip()
        if not kb_uuid or kb_uuid in seen:
            continue
        seen.add(kb_uuid)
        unique_uuids.append(kb_uuid)
    if not unique_uuids:
        return {}
    if len(unique_uuids) > 100:
        raise HTTPException(status_code=400, detail="Too many knowledge base ids.")

    all_kbs = svc.list_all_unfiltered()
    kb_id_by_uuid = {kb.uuid: kb.id for kb in all_kbs if kb.id is not None}
    if user.role != "owner":
        allowed_ids = svc.get_trainable_kb_ids(user.id, user.role)
        for kb_uuid in unique_uuids:
            kb_id = kb_id_by_uuid.get(kb_uuid)
            if kb_id is not None and kb_id not in allowed_ids:
                raise HTTPException(status_code=403, detail="No permission to manage one or more knowledge bases")

    items_by_kb = svc.get_permissions_with_users_batch(unique_uuids)
    return {
        kb_uuid: [KBPermissionOut.model_validate(x) for x in (items_by_kb.get(kb_uuid) or [])]
        for kb_uuid in unique_uuids
    }


@router.put("/kb/{uuid}/permissions")
@limiter.limit("20/minute")
def set_kb_permissions(
    request: Request,
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
        return svc.update(
            uuid,
            data.name,
            data.description,
            personal_data_mode=data.personal_data_mode,
        )
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


def _handle_openai_error(e: Exception) -> None:
    """OpenAI (embedding) hibák → 502, felhasználónak érthető üzenettel."""
    if isinstance(e, OpenAIAuthError):
        raise HTTPException(
            status_code=502,
            detail="A tanítás az embedding szolgáltatás hibája miatt nem sikerült (érvénytelen API kulcs). A rendszergazda ellenőrizze a szerver OPENAI_API_KEY beállítását.",
        ) from e
    if isinstance(e, OpenAIAPIError):
        raise HTTPException(
            status_code=502,
            detail="A tanítás az embedding szolgáltatás átmeneti elérhetetlensége miatt nem sikerült. Próbáld később újra.",
        ) from e


def _handle_pii_engine_error(e: Exception) -> None:
    """PII engine hiba esetén fail-closed, érthető 503 válasszal."""
    raise HTTPException(
        status_code=503,
        detail="A személyesadat-szűrés átmenetileg nem elérhető, ezért a feltöltést biztonsági okból leállítottuk. Próbáld később újra.",
    ) from e


def _validate_upload_size(file: UploadFile) -> None:
    max_mb = int(getattr(settings, "kb_upload_max_mb", 10) or 10)
    max_bytes = max_mb * 1024 * 1024
    try:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
    except Exception:
        size = None
    if size is not None and size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"A feltöltött fájl túl nagy. Maximum: {max_mb} MB.",
        )


def _validate_upload_type(file: UploadFile) -> None:
    filename = (file.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Nem támogatott fájltípus. Engedélyezett: pdf, docx, txt, csv, xlsx, xls.",
        )
    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in _ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="A feltöltött fájl MIME típusa nem engedélyezett.",
        )


# --- TRAIN TEXT (nyers szöveg) ---
@router.post("/kb/{uuid}/train")
@limiter.limit("15/minute")
async def train_raw_text(
    request: Request,
    uuid: str,
    data: KBTrainRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    try:
        return await svc.add_block(
            uuid,
            data.title or "",
            data.content,
            current_user_id=user.id,
            confirm_pii=data.confirm_pii,
            pii_review_decision=getattr(data, "pii_review_decision", None),
            pii_decisions=getattr(data, "pii_decisions", None),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PiiConfirmationRequiredError as e:
        _raise_pii_review_409(e)
    except RuntimeError as ex:
        _handle_pii_engine_error(ex)
    except (OpenAIAuthError, OpenAIAPIError) as ex:
        _handle_openai_error(ex)


def _pii_review_detail(e: PiiConfirmationRequiredError) -> dict:
    """Build rich 409 payload: entity types, counts, preview snippets, matches (context)."""
    detail = {
        "requires_pii_confirmation": True,
        "message": "Személyes adatok észlelve; erősítsd meg a folytatáshoz.",
        "detected_types": e.detected_types,
        "entity_types": e.detected_types,
        "counts": getattr(e, "counts", None) or {},
        "snippets": getattr(e, "snippets", None) or [],
        "matches": getattr(e, "matches", None) or [],
    }
    return detail


def _raise_pii_review_409(e: PiiConfirmationRequiredError) -> None:
    raise HTTPException(status_code=409, detail=_pii_review_detail(e))


# --- TRAIN TEXT (külön endpoint, ha kell) ---
@router.post("/kb/{uuid}/train/text")
@limiter.limit("15/minute")
async def train_text(
    request: Request,
    uuid: str,
    data: KBTrainRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    try:
        return await svc.add_block(
            uuid,
            data.title or "",
            data.content,
            current_user_id=user.id,
            confirm_pii=data.confirm_pii,
            pii_review_decision=getattr(data, "pii_review_decision", None),
            pii_decisions=getattr(data, "pii_decisions", None),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PiiConfirmationRequiredError as e:
        _raise_pii_review_409(e)
    except RuntimeError as ex:
        _handle_pii_engine_error(ex)
    except (OpenAIAuthError, OpenAIAPIError) as ex:
        _handle_openai_error(ex)


# --- TRAIN FILE ---
@router.post("/kb/{uuid}/train/file")
@limiter.limit("10/minute")
async def train_file(
    request: Request,
    uuid: str,
    file: UploadFile = File(...),
    confirm_pii: bool = Form(False),
    pii_review_decision: Optional[str] = Form(None),
    pii_decisions: Optional[str] = Form(None),  # JSON string: [{"index":0,"decision":"delete"},...]
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    _validate_upload_type(file)
    _validate_upload_size(file)
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    pii_decisions_list = None
    if pii_decisions:
        try:
            pii_decisions_list = json.loads(pii_decisions)
        except (ValueError, TypeError):
            pass
    try:
        return await svc.train_from_file(
            uuid,
            file,
            current_user_id=user.id,
            confirm_pii=confirm_pii,
            pii_review_decision=pii_review_decision,
            pii_decisions=pii_decisions_list,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PiiConfirmationRequiredError as e:
        _raise_pii_review_409(e)
    except RuntimeError as ex:
        _handle_pii_engine_error(ex)
    except (OpenAIAuthError, OpenAIAPIError) as ex:
        _handle_openai_error(ex)


# --- TRAIN LOG (lista + törlés) ---
@router.get("/kb/{uuid}/train/log")
@limiter.limit("30/minute")
def get_training_log(
    request: Request,
    uuid: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
    include_raw_content: bool = False,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """Tanítási napló: ki, mikor, milyen címmel/tartalommal tanított. Csak train joggal."""
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to view this knowledge base")
    # Nyers tartalom csak ownernek kérhető explicit módon.
    allow_raw = include_raw_content and user.role == "owner"
    return svc.list_training_log(uuid, limit=limit, offset=offset, include_raw_content=allow_raw)


@router.delete("/kb/{uuid}/train/points/{point_id}")
async def delete_training_point(
    request: Request,
    uuid: str,
    point_id: str,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    audit_service=Depends(get_audit_service),
    user: User = Depends(get_current_user),
):
    """Egy tanítási bejegyzés törlése a naplóból és a vektortárból. Csak train joggal."""
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to manage this knowledge base")
    try:
        await svc.delete_training_point(uuid, point_id)
        try:
            audit_service.log(
                "pii_personal_data_deleted",
                user_id=user.id,
                details={"kb_uuid": uuid, "point_id": point_id, "reason": "training_point_deleted"},
                ip=getattr(request.client, "host", None) if request.client else None,
                user_agent=request.headers.get("user-agent"),
                tenant_slug=getattr(request.state, "tenant_slug", None),
            )
        except Exception:
            pass
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/kb/{uuid}/train/points/{point_id}/pii")
@limiter.limit("15/minute")
def get_point_personal_data(
    request: Request,
    uuid: str,
    point_id: str,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    audit_service=Depends(get_audit_service),
    user: User = Depends(get_current_user),
):
    """PII adatok lekérése egy tanítási bejegyzéshez. Csak ownernek engedett."""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can view personal data records")
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to view this knowledge base")
    try:
        rows = svc.list_personal_data_for_point(uuid, point_id)
        try:
            audit_service.log(
                "pii_personal_data_viewed",
                user_id=user.id,
                details={"kb_uuid": uuid, "point_id": point_id, "result_count": len(rows)},
                ip=getattr(request.client, "host", None) if request.client else None,
                user_agent=request.headers.get("user-agent"),
                tenant_slug=getattr(request.state, "tenant_slug", None),
            )
        except Exception:
            pass
        return rows
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/{uuid}/dsar/search")
@limiter.limit("10/minute")
def dsar_search(
    request: Request,
    uuid: str,
    data: KBDsarSearchRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    audit_service=Depends(get_audit_service),
    user: User = Depends(get_current_user),
):
    """DSAR keresés PII rekordokban. Csak ownernek."""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can run DSAR search")
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to access this knowledge base")
    try:
        result = svc.dsar_search(uuid, query=data.query, limit=data.limit, scan_limit=data.scan_limit)
        try:
            audit_service.log(
                "dsar_search",
                user_id=user.id,
                details={
                    "kb_uuid": uuid,
                    "query_hash": result.get("query_hash"),
                    "matched": result.get("matched"),
                    "scanned": result.get("scanned"),
                },
                ip=getattr(request.client, "host", None) if request.client else None,
                user_agent=request.headers.get("user-agent"),
                tenant_slug=getattr(request.state, "tenant_slug", None),
            )
        except Exception:
            pass
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/{uuid}/dsar/export")
@limiter.limit("10/minute")
def dsar_export(
    request: Request,
    uuid: str,
    data: KBDsarSearchRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    audit_service=Depends(get_audit_service),
    user: User = Depends(get_current_user),
):
    """DSAR export (MVP) – ugyanaz a találati lista export célra. Csak ownernek."""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can run DSAR export")
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to access this knowledge base")
    try:
        result = svc.dsar_search(uuid, query=data.query, limit=data.limit, scan_limit=data.scan_limit)
        try:
            audit_service.log(
                "dsar_export",
                user_id=user.id,
                details={
                    "kb_uuid": uuid,
                    "query_hash": result.get("query_hash"),
                    "matched": result.get("matched"),
                    "scanned": result.get("scanned"),
                },
                ip=getattr(request.client, "host", None) if request.client else None,
                user_agent=request.headers.get("user-agent"),
                tenant_slug=getattr(request.state, "tenant_slug", None),
            )
        except Exception:
            pass
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/kb/{uuid}/dsar/delete")
@limiter.limit("5/minute")
def dsar_delete(
    request: Request,
    uuid: str,
    data: KBDsarDeleteRequest,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    audit_service=Depends(get_audit_service),
    user: User = Depends(get_current_user),
):
    """DSAR törlés PII rekordokra. Csak ownernek."""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can run DSAR delete")
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to access this knowledge base")
    try:
        result = svc.dsar_delete(
            uuid,
            query=data.query,
            limit=data.limit,
            scan_limit=data.scan_limit,
            dry_run=data.dry_run,
        )
        try:
            audit_service.log(
                "dsar_delete",
                user_id=user.id,
                details={
                    "kb_uuid": uuid,
                    "query_hash": result.get("query_hash"),
                    "matched": result.get("matched"),
                    "deleted": result.get("deleted"),
                    "dry_run": result.get("dry_run"),
                },
                ip=getattr(request.client, "host", None) if request.client else None,
                user_agent=request.headers.get("user-agent"),
                tenant_slug=getattr(request.state, "tenant_slug", None),
            )
        except Exception:
            pass
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/kb/{uuid}/pii/metrics")
@limiter.limit("20/minute")
def get_pii_metrics(
    request: Request,
    uuid: str,
    svc: KnowledgeBaseService = Depends(get_kb_service),
    user: User = Depends(get_current_user),
):
    """PII dashboard alap metrikák. Csak ownernek."""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can view PII metrics")
    if not svc.user_can_train(uuid, user.id, user.role):
        raise HTTPException(status_code=403, detail="No permission to access this knowledge base")
    try:
        return svc.personal_data_metrics(uuid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
