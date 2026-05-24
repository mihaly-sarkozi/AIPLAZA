# backend/apps/chat/router/channel_credentials_router.py
# Feladat: Channel credential admin HTTP endpointok FastAPI adaptere.

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.chat.bootstrap.dependencies import get_chat_service
from apps.chat.application.channel_request_policy import (
    channel_access_service_or_503 as _channel_access_service_or_503,
    parse_iso_datetime as _parse_iso_datetime,
    tenant_required_id as _tenant_required_id,
)
from apps.chat.router.chat_requests import (
    ChannelCredentialCreateRequest,
    ChannelCredentialPolicyUpdateRequest,
)
from apps.chat.application.chat_payload_policy import tenant_chat_limits as _tenant_chat_limits
from apps.chat.application.http_use_cases import (
    audit_channel_credential_created,
    audit_channel_credential_revoked,
    audit_channel_credential_rotated,
)
from core.kernel.audit import AuditPort
from core.kernel.deps.facade import get_audit_service
from core.kernel.http.responses import OperationStatusResponse
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.modules.users.domain.dto import User

router = APIRouter()


@router.post("/channel/credentials")
@limiter.limit("20/minute")
async def create_channel_credential(
    request: Request,
    payload: ChannelCredentialCreateRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    audit: AuditPort = Depends(get_audit_service),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    limits = _tenant_chat_limits(tenant)
    if int(payload.daily_limit) > int(limits["channel_daily_limit_cap"]):
        raise HTTPException(status_code=400, detail="A napi limit túl magas ehhez a csomaghoz.")
    if int(payload.per_minute_limit) > int(limits["channel_per_minute_limit_cap"]):
        raise HTTPException(status_code=400, detail="A per-minute limit túl magas ehhez a csomaghoz.")
    try:
        created = channel_svc.create_credential(
            tenant_id=tenant_id,
            channel_type=str(payload.channel_type or "widget").strip().lower(),
            name=payload.name,
            allowed_kb_uuids=payload.allowed_kb_uuids,
            daily_limit=payload.daily_limit,
            per_minute_limit=payload.per_minute_limit,
            allowed_origins=payload.allowed_origins,
            allowed_ip_ranges=payload.allowed_ip_ranges,
            require_signed_requests=payload.require_signed_requests,
            expires_at=_parse_iso_datetime(payload.expires_at),
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_channel_credential_created(
        audit=audit,
        user_id=current_user.id,
        tenant_id=tenant_id,
        created=created,
    )
    return {"item": created, "warning": None}


@router.get("/channel/credentials")
@limiter.limit("60/minute")
async def list_channel_credentials(
    request: Request,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"items": channel_svc.list_credentials(tenant_id=tenant_id)}


@router.post("/channel/credentials/{credential_id}/rotate")
@limiter.limit("20/minute")
async def rotate_channel_credential(
    request: Request,
    credential_id: int,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    audit: AuditPort = Depends(get_audit_service),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    rotated = channel_svc.rotate_credential(
        tenant_id=tenant_id,
        credential_id=credential_id,
        rotated_by=current_user.id,
    )
    if rotated is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    audit_channel_credential_rotated(
        audit=audit,
        user_id=current_user.id,
        tenant_id=tenant_id,
        credential_id=credential_id,
        rotated=rotated,
    )
    return {"item": rotated}


@router.post("/channel/credentials/{credential_id}/revoke", response_model=OperationStatusResponse)
@limiter.limit("20/minute")
async def revoke_channel_credential(
    request: Request,
    credential_id: int,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    audit: AuditPort = Depends(get_audit_service),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    if not channel_svc.revoke_credential(tenant_id=tenant_id, credential_id=credential_id, revoked_by=current_user.id):
        raise HTTPException(status_code=404, detail="Credential not found")
    audit_channel_credential_revoked(
        audit=audit,
        user_id=current_user.id,
        tenant_id=tenant_id,
        credential_id=credential_id,
    )
    return OperationStatusResponse()


@router.put("/channel/credentials/{credential_id}/policy")
@limiter.limit("30/minute")
async def update_channel_credential_policy(
    request: Request,
    credential_id: int,
    payload: ChannelCredentialPolicyUpdateRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    limits = _tenant_chat_limits(tenant)
    if payload.daily_limit is not None and int(payload.daily_limit) > int(limits["channel_daily_limit_cap"]):
        raise HTTPException(status_code=400, detail="A napi limit túl magas ehhez a csomaghoz.")
    if payload.per_minute_limit is not None and int(payload.per_minute_limit) > int(limits["channel_per_minute_limit_cap"]):
        raise HTTPException(status_code=400, detail="A per-minute limit túl magas ehhez a csomaghoz.")
    try:
        updated = channel_svc.update_policy(
            tenant_id=tenant_id,
            credential_id=credential_id,
            allowed_kb_uuids=payload.allowed_kb_uuids,
            daily_limit=payload.daily_limit,
            per_minute_limit=payload.per_minute_limit,
            allowed_origins=payload.allowed_origins,
            allowed_ip_ranges=payload.allowed_ip_ranges,
            require_signed_requests=payload.require_signed_requests,
            updated_by=current_user.id,
            expires_at=_parse_iso_datetime(payload.expires_at),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"item": updated}


@router.get("/channel/credentials/{credential_id}/instructions")
@limiter.limit("60/minute")
async def channel_credential_instructions(
    request: Request,
    credential_id: int,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    items = channel_svc.list_credentials(tenant_id=tenant_id)
    item = next((row for row in items if int(row.get("id") or 0) == credential_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    endpoint = f"{request.base_url}api/channel/chat".replace("//api", "/api")
    embed_snippet = (
        "<script src=\"https://cdn.aiplaza/widget.js\" "
        f"data-endpoint=\"{endpoint}\" data-key=\"<GENERATED_SECRET>\" "
        f"data-tenant=\"{getattr(tenant, 'slug', '') or ''}\"></script>"
    )
    return {
        "credential_id": credential_id,
        "channel_type": item.get("channel_type"),
        "endpoint": endpoint,
        "widget_embed_snippet": embed_snippet,
        "api_example": {
            "curl": (
                f"curl -X POST '{endpoint}' "
                "-H 'Authorization: Bearer <GENERATED_SECRET>' "
                "-H 'Content-Type: application/json' "
                f"-d '{json.dumps({'question': 'Mit tud a tudástár?', 'kb_uuid': None})}'"
            )
        },
    }


__all__ = ["router"]
