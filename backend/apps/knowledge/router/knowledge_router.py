# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from apps.di import get_factory
from apps.knowledge.dependencies import CurrentKnowledgeUserDep, KnowledgeFacadeDep, KnowledgeTenantDep
from apps.knowledge.training_ingest import build_sentence_rows
from core.di import get_login_service, get_service
from core.kernel.config import app_settings
from core.kernel.config.environment import get_app_env
from core.kernel.security.rate_limit import limiter
from shared.documents.text_extraction import extract_text_from_upload
from shared.text.chunking import chunk_text_for_training

from apps.knowledge.router.knowledge_requests import (
    KBCreate,
    KBUpdate,
    KBDelete,
    KBPermissionsUpdate,
    KBBatchPermissionsRequest,
    IngestTrainingTextRequest,
)
from apps.knowledge.router.knowledge_response import KBOut, KBPermissionOut

from core.platform.auth.auth_dependencies import require_permission
from apps.contracts.service_keys import MODULE_KNOWLEDGE_QDRANT_FACTORY
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from apps.knowledge.ports.repositories import KbPermissionItem
from core.capabilities.users.dto import User

router = APIRouter()


# Ez a függvény a(z) permissions_from_create logikáját valósítja meg.
def _permissions_from_create(data: KBCreate) -> list[KbPermissionItem]:
    if not data.permissions:
        return []
    return [
        (p["user_id"], p.get("permission") or "none")
        for p in data.permissions
        if isinstance(p, dict) and "user_id" in p
    ]


def _ensure_training_mfa(user: User) -> None:
    if not bool(getattr(app_settings, "training_mfa_required", True)):
        return
    login_service = get_login_service()
    status = login_service.authenticator_status(int(getattr(user, "id", 0) or 0))
    if not bool(status.get("enabled")):
        raise HTTPException(
            status_code=403,
            detail="MFA kötelező a tanítási műveletekhez. Aktiváld az authenticator MFA-t.",
        )


@router.get("/kb", response_model=list[KBOut])
def list_kb(
    request: Request,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
):
    """Lista: admin/owner mindent lát; user csak azt, amire use/train joga van. can_train = user taníthatja-e."""
    kbs = svc.list_all(current_user_id=user.id, current_user=user)
    trainable_ids = svc.get_trainable_kb_ids(user.id, user)
    def _has_training(kb_uuid: str) -> bool:
        try:
            return bool(svc.list_ingest_runs(kb_uuid, limit=1))
        except Exception:
            return False

    def _storage_metrics(kb) -> dict:
        try:
            value = svc.storage_metrics_for_corpus(kb)
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    rows: list[KBOut] = []
    for kb in kbs:
        deleted_at = getattr(kb, "deleted_at", None)
        is_deleted = deleted_at is not None
        storage_metrics = _storage_metrics(kb)
        training_char_count = int(
            storage_metrics.get("training_char_count")
            or getattr(kb, "deleted_training_char_count", 0)
            or 0
        )
        if is_deleted and training_char_count <= 0:
            continue
        rows.append(
            KBOut(
                uuid=kb.uuid,
                name=kb.name,
                description=kb.description,
                qdrant_collection_name=kb.qdrant_collection_name,
                personal_data_mode=getattr(kb, "personal_data_mode", None) or "no_personal_data",
                personal_data_sensitivity=getattr(kb, "personal_data_sensitivity", None) or "medium",
                pii_depersonalization_enabled=bool(getattr(kb, "pii_depersonalization_enabled", True)),
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                deleted_at=deleted_at,
                status="deleted" if is_deleted else "active",
                can_train=bool(
                    not is_deleted
                    and getattr(kb, "id", None) is not None
                    and getattr(kb, "id", None) in trainable_ids
                ),
                has_training=training_char_count > 0 if is_deleted else _has_training(kb.uuid),
                storage_metrics=storage_metrics,
            )
        )
    return sorted(rows, key=lambda row: row.deleted_at is not None)


# Ez a függvény létrehozza a(z) KB logikáját.
@router.post("/kb", response_model=KBOut)
@limiter.limit("5/minute")
def create_kb(
    request: Request,
    data: KBCreate,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: User = Depends(require_permission("knowledge.write")),
):
    try:
        usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
        allowed, reason = usage_service.can_create_kb(tenant)
        if not allowed:
            raise HTTPException(status_code=400, detail=reason)
        perms = _permissions_from_create(data)
        return svc.create(
            data.name, data.description,
            permissions=perms if perms else None,
            current_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/kb/{uuid}/permissions", response_model=list[KBPermissionOut])
@limiter.limit("30/minute")
def get_kb_permissions(
    request: Request,
    uuid: str,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
):
    """Összes felhasználó és jogosultság (use/train/none) ehhez a tudástárhoz. Csak train joggal."""
    if not svc.user_can_train(uuid, user.id, user):
        raise HTTPException(status_code=403, detail="No permission to manage this knowledge base")
    items = svc.get_permissions_with_users(uuid)
    return [KBPermissionOut.model_validate(x) for x in items]


# Ez a függvény visszaadja a(z) KB permissions batch logikáját.
@router.post("/kb/permissions/batch")
@limiter.limit("20/minute")
def get_kb_permissions_batch(
    request: Request,
    data: KBBatchPermissionsRequest,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
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
        allowed_ids = svc.get_trainable_kb_ids(user.id, user)
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
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
):
    """Jogosultságok beállítása: minden felhasználóhoz use/train/none. Csak train joggal; saját jogot nem lehet none-ra állítani."""
    if not svc.user_can_train(uuid, user.id, user):
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
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
):
    """Név/leírás szerkesztése: csak ha train joga van a tudástárhoz."""
    if not svc.user_can_train(uuid, user.id, user):
        raise HTTPException(status_code=403, detail="No permission to edit this knowledge base")
    try:
        return svc.update(
            uuid,
            data.name,
            data.description,
            personal_data_mode=data.personal_data_mode,
            pii_depersonalization_enabled=data.pii_depersonalization_enabled,
            current_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Ez a függvény törli a(z) KB logikáját.
_MAX_TRAINING_UPLOAD_BYTES = 20 * 1024 * 1024
_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


def _ensure_legacy_ingest_enabled() -> None:
    if bool(getattr(app_settings, "legacy_knowledge_ingest_enabled", False)):
        return
    raise HTTPException(
        status_code=410,
        detail=(
            "A legacy ingest útvonal le van tiltva. "
            "Használd az új /knowledge/corpora/{corpus_uuid}/ingest/... API-t."
        ),
    )


async def _read_upload_with_limit(upload: UploadFile, *, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=400, detail="File too large (max 20 MB).")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/kb/{uuid}/ingest-training")
@limiter.limit("15/minute")
async def ingest_training_text(
    request: Request,
    uuid: str,
    body: IngestTrainingTextRequest,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
):
    """Egyszerű szöveges tanítás: mondat chunkok Qdrant sentence pontokként."""
    _ensure_legacy_ingest_enabled()
    if not svc.user_can_train(uuid, user.id, user):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    _ensure_training_mfa(user)
    collection = svc.qdrant_collection_for_uuid(uuid)
    if not collection:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    text = (body.text or "").strip()
    if len(text) < 30:
        raise HTTPException(status_code=400, detail="Text too short for training (min ~30 characters).")
    chunks = chunk_text_for_training(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No usable text chunks after processing.")
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    allowed, reason = usage_service.can_consume_training_chars(tenant, len(text))
    if not allowed:
        raise HTTPException(status_code=402, detail=reason or "Training quota exceeded")
    qdrant = get_factory(MODULE_KNOWLEDGE_QDRANT_FACTORY)()
    await qdrant.ensure_collection_schema_async(collection)
    rows = build_sentence_rows(chunks, body.title)
    await qdrant.upsert_sentence_points(collection, rows)
    usage_service.record_training_ingest(
        tenant,
        char_count=len(text),
        storage_bytes=len(text.encode("utf-8")),
    )
    return {"ok": True, "chunks": len(chunks)}


@router.post("/kb/{uuid}/ingest-training-file")
@limiter.limit("10/minute")
async def ingest_training_file(
    request: Request,
    uuid: str,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: CurrentKnowledgeUserDep,
    file: UploadFile = File(...),
):
    _ensure_legacy_ingest_enabled()
    if not svc.user_can_train(uuid, user.id, user):
        raise HTTPException(status_code=403, detail="No permission to train this knowledge base")
    _ensure_training_mfa(user)
    collection = svc.qdrant_collection_for_uuid(uuid)
    if not collection:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    raw = await _read_upload_with_limit(file, max_bytes=_MAX_TRAINING_UPLOAD_BYTES)
    try:
        text = extract_text_from_upload(file.filename or "upload.txt", raw)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use .txt, .pdf, or .docx.",
        )
    text = text.strip()
    if len(text) < 30:
        raise HTTPException(status_code=400, detail="Extracted text too short for training.")
    chunks = chunk_text_for_training(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No usable text chunks after processing.")
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    allowed, reason = usage_service.can_consume_training_chars(tenant, len(text))
    if not allowed:
        raise HTTPException(status_code=402, detail=reason or "Training quota exceeded")
    qdrant = get_factory(MODULE_KNOWLEDGE_QDRANT_FACTORY)()
    await qdrant.ensure_collection_schema_async(collection)
    title = (file.filename or "").rsplit(".", 1)[0][:200] or None
    rows = build_sentence_rows(chunks, title)
    await qdrant.upsert_sentence_points(collection, rows)
    usage_service.record_training_ingest(
        tenant,
        char_count=len(text),
        storage_bytes=len(raw),
    )
    return {"ok": True, "chunks": len(chunks)}


@router.delete("/kb/{uuid}")
def delete_kb(
    request: Request,
    uuid: str,
    data: KBDelete,
    tenant: KnowledgeTenantDep,
    svc: KnowledgeFacadeDep,
    user: User = Depends(require_permission("knowledge.write")),
):
    try:
        demo_mode = bool(
            tenant.config
            and tenant.config.feature_flags
            and bool(tenant.config.feature_flags.get("demo_mode"))
        )
        if get_app_env() != "dev" and not demo_mode:
            raise HTTPException(status_code=403, detail="Knowledge base deletion is available only in dev mode or free test mode")
        svc.delete(uuid, data.confirm_name, demo_mode=demo_mode)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


