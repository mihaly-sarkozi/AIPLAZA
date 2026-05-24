# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from fastapi import APIRouter, Depends, HTTPException, Request

from apps.knowledge.bootstrap.dependencies import CurrentKnowledgeUserDep, KnowledgeFacadeDep, KnowledgeTenantDep
from apps.knowledge.api.upload_support import (
    ensure_training_mfa as _ensure_training_mfa,
    ensure_training_quota as _ensure_training_quota,
    record_training_usage as _record_training_usage,
)
from core.kernel.deps.facade import get_service
from core.kernel.config.config_loader import get_app_env
from core.kernel.http.responses import OperationStatusResponse
from core.kernel.http.security_errors import security_http_exception
from core.kernel.security.rate_limit import limiter

from apps.knowledge.router.knowledge_requests import (
    KBCreate,
    KBUpdate,
    KBDelete,
    KBPermissionsUpdate,
    KBBatchPermissionsRequest,
)
from apps.knowledge.router.knowledge_response import KBOut, KBPermissionOut

from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from apps.knowledge.ports.repositories import KbPermissionItem
from core.modules.users.domain.dto import User

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
        raise security_http_exception()
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

    kb_by_uuid = {kb.uuid: kb for kb in svc.list_all_unfiltered()}
    for kb_uuid in unique_uuids:
        kb = kb_by_uuid.get(kb_uuid)
        if kb is not None and not svc.can_train_knowledge_base(user, kb):
            raise security_http_exception()

    items_by_kb = svc.get_permissions_with_users_batch(unique_uuids)
    return {
        kb_uuid: [KBPermissionOut.model_validate(x) for x in (items_by_kb.get(kb_uuid) or [])]
        for kb_uuid in unique_uuids
    }


@router.put("/kb/{uuid}/permissions", response_model=OperationStatusResponse)
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
        raise security_http_exception()
    perms: list[KbPermissionItem] = [(p.user_id, p.permission) for p in data.permissions]
    try:
        svc.set_permissions(uuid, perms, current_user_id=user.id)
        return OperationStatusResponse()
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
        raise security_http_exception()
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


@router.delete("/kb/{uuid}", response_model=OperationStatusResponse)
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
        return OperationStatusResponse()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


