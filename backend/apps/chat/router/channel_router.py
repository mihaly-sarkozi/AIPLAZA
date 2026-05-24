# backend/apps/chat/router/channel_router.py
# Feladat: Channel runtime chat, feedback es analytics HTTP endpointok FastAPI
# adaptere. Credential admin endpointok a channel_credentials_router modulban vannak.

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response as MutableResponse

from apps.chat.bootstrap.dependencies import get_chat_service
from apps.chat.application.channel_request_policy import (
    channel_access_service_or_503 as _channel_access_service_or_503,
    extract_channel_secret as _extract_channel_secret,
    tenant_required_id as _tenant_required_id,
)
from apps.chat.router.chat_requests import (
    ChannelAskRequest,
    ChannelFeedbackCaptureRequest,
    ChannelFeedbackTriageRequest,
)
from apps.chat.router.chat_response import AskResponse
from apps.chat.service.channel_chat_use_case import ChannelChatUseCase
from apps.chat.service.chat_permission_service import ChatPermissionService
from core.kernel.audit import AuditPort
from core.kernel.deps.facade import get_audit_service
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.kernel.http.security_errors import security_http_exception
from core.kernel.interface.observability import increment_metric
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.modules.users.domain.dto import User

router = APIRouter()
channel_chat_use_case = ChannelChatUseCase()
chat_permission_service = ChatPermissionService()


@router.post(
    "/channel/chat",
    response_model=AskResponse,
    response_model_exclude_none=True,
)
@limiter.limit("120/minute")
async def channel_chat(
    request: Request,
    req: ChannelAskRequest,
    tenant: RequiredTenantContextDep,
    response: MutableResponse,
    audit: AuditPort = Depends(get_audit_service),
    svc=Depends(get_chat_service),
):
    return await channel_chat_use_case.execute(
        request=request,
        req=req,
        tenant=tenant,
        response=response,
        audit=audit,
        svc=svc,
    )


@router.post("/channel/feedback")
@limiter.limit("180/minute")
async def channel_feedback_capture(
    request: Request,
    payload: ChannelFeedbackCaptureRequest,
    tenant: RequiredTenantContextDep,
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    secret = _extract_channel_secret(request)
    principal = channel_svc.authenticate(
        tenant_id=tenant_id,
        secret=secret,
        origin=request.headers.get("Origin"),
    )
    if not chat_permission_service.can_send_channel_message(principal, "widget", tenant):
        increment_metric("channel.feedback.rejected.auth", 1.0)
        raise security_http_exception(status_code=401, code="UNAUTHORIZED", message="Authentication failed.")
    result = channel_svc.record_feedback(
        tenant_id=tenant_id,
        credential_id=principal.credential_id,
        channel_type=principal.channel_type,
        query_run_id=payload.query_run_id,
        trace_id=payload.trace_id,
        helpful=payload.helpful,
        reason=payload.reason,
        note=payload.note,
    )
    increment_metric("channel.feedback.count", 1.0)
    return {"item": result}


@router.post("/channel/feedback/{feedback_id}/triage")
@limiter.limit("60/minute")
async def channel_feedback_triage(
    request: Request,
    feedback_id: int,
    payload: ChannelFeedbackTriageRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(require_permission("chat.channel.manage")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    updated = channel_svc.triage_feedback(
        tenant_id=tenant_id,
        feedback_id=feedback_id,
        triage_status=payload.triage_status,
        triage_owner=payload.triage_owner,
        triage_note=payload.triage_note,
        triaged_by=current_user.id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"item": updated}


@router.get("/channel/analytics/summary")
@limiter.limit("120/minute")
async def channel_analytics_summary(
    request: Request,
    tenant: RequiredTenantContextDep,
    days: int = 14,
    current_user: User = Depends(require_permission("chat.channel.analytics")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"summary": channel_svc.analytics_summary(tenant_id=tenant_id, days=days)}


@router.get("/channel/analytics/events")
@limiter.limit("120/minute")
async def channel_analytics_events(
    request: Request,
    tenant: RequiredTenantContextDep,
    limit: int = 100,
    current_user: User = Depends(require_permission("chat.channel.analytics")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"items": channel_svc.analytics_events(tenant_id=tenant_id, limit=limit)}


@router.get("/channel/analytics/feedback")
@limiter.limit("120/minute")
async def channel_analytics_feedback(
    request: Request,
    tenant: RequiredTenantContextDep,
    limit: int = 100,
    current_user: User = Depends(require_permission("chat.channel.analytics")),
    svc=Depends(get_chat_service),
):
    channel_svc = _channel_access_service_or_503(svc)
    tenant_id = _tenant_required_id(tenant)
    return {"items": channel_svc.analytics_feedback(tenant_id=tenant_id, limit=limit)}


__all__ = ["router"]
