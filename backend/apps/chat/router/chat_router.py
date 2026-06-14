# backend/apps/chat/router/chat_router.py
# Feladat: A chat app HTTP és websocket route-jait komponálja. A websocket limitek, chat payload policy és channel session helper logikák külön support modulokba kerültek, itt a route handler orchestration és kompatibilis router export marad. Program-specifikus chat API belépési pont.
# Sárközi Mihály - 2026.05.21

import asyncio
import json
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from apps.chat.bootstrap.dependencies import get_chat_service
from apps.chat.application.chat_payload_policy import (
    tenant_chat_limits as _tenant_chat_limits,
)
from apps.chat.errors import ChatPermissionDenied
from apps.chat.router.websocket_limits import (
    ws_allow_message as _ws_allow_message,
    ws_enabled as _ws_enabled,
    ws_idle_timeout_sec as _ws_idle_timeout_sec,
    ws_max_message_chars as _ws_max_message_chars,
    ws_release_connection as _ws_release_connection,
    ws_try_acquire_connection as _ws_try_acquire_connection,
)
from core.kernel.config.config_loader import settings
from core.kernel.deps.facade import get_service, get_tenant_repository
from core.kernel.http.responses import OperationStatus, OperationStatusResponse
from core.kernel.http.tenant_dependencies import RequiredTenantContextDep
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.security.rate_limit import limiter
from core.kernel.interface.observability import increment_metric
from core.modules.users.domain.dto import User
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user, validate_ws_token
from core.kernel.security.cookie_policy import (
    set_ws_token_cookie,
)

from apps.chat.router.chat_requests import (
    AskRequest,
    ChatFeedbackRequest,
)
from apps.chat.router.chat_response import AskResponse
from apps.chat.application.http_use_cases import (
    handle_chat_request,
    handle_ws_chat_message,
)
from apps.chat.service.chat_service import PiiDepersonalizationUnavailableError

router = APIRouter()


@router.get("/chat/ws-token")
@limiter.limit("60/minute")
async def chat_ws_token(
    request: Request,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
):
    """
    WebSocket auth: Bearer token → ws_token HttpOnly cookie (rövid életű).
    A frontend ezt hívja credentials-szel; utána a /chat/ws kapcsolat a cookie-t küldi (token nem kerül URL-be/logokba).
    """
    if not _ws_enabled():
        raise HTTPException(status_code=503, detail="Websocket chat le van tiltva.")
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    response = Response(status_code=204)
    set_ws_token_cookie(
        response,
        token,
        secure=settings.cookie_secure,
        samesite=getattr(settings, "cookie_samesite", "lax"),
    )
    return response


# Ez az aszinkron függvény a(z) chat logikáját valósítja meg.
@router.post(
    "/chat",
    response_model=AskResponse,
    response_model_exclude_none=True,
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: AskRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    return await handle_chat_request(req=req, tenant=tenant, current_user=current_user, svc=svc)


@router.post("/chat/feedback", response_model=OperationStatusResponse)
@limiter.limit("60/minute")
async def chat_feedback(
    request: Request,
    req: ChatFeedbackRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    if not hasattr(svc, "capture_retrieval_feedback"):
        return OperationStatusResponse(status=OperationStatus.SKIPPED, reason="feedback_service_not_available")
    result = svc.capture_retrieval_feedback(
        trace_id=req.trace_id,
        helpful=req.helpful,
        note=req.note,
    )
    status = str((result or {}).get("status") or OperationStatus.OK).lower()
    reason = str((result or {}).get("reason") or "").strip() or None
    if status == OperationStatus.SKIPPED.value:
        return OperationStatusResponse(status=OperationStatus.SKIPPED, reason=reason)
    return OperationStatusResponse(details=dict(result or {}))


@router.post("/chat/sessions")
@limiter.limit("30/minute")
async def create_chat_session(
    request: Request,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    session_service = getattr(svc, "chat_session_service", None)
    if session_service is None:
        raise HTTPException(status_code=503, detail="Chat session storage unavailable")
    session_id, _history = session_service.resolve_or_create_session(
        conversation_id=None,
        tenant_slug=getattr(tenant, "slug", None),
        user_id=current_user.id,
        kb_uuid=None,
        channel_id="web",
    )
    return {"conversation_id": session_id}


@router.get("/chat/sessions/{session_id}")
@limiter.limit("60/minute")
async def get_chat_session(
    request: Request,
    session_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    session_service = getattr(svc, "chat_session_service", None)
    if session_service is None:
        raise HTTPException(status_code=503, detail="Chat session storage unavailable")
    payload = session_service.get_session_payload(session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return payload


@router.get("/chat/query-runs/{query_run_id}/sources")
@limiter.limit("60/minute")
async def get_query_run_sources(
    request: Request,
    query_run_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    retrieval = getattr(svc, "retrieval_service", None)
    if retrieval is None or not hasattr(retrieval, "get_query_context_download"):
        raise HTTPException(status_code=404, detail="Sources not found")
    download = retrieval.get_query_context_download(query_run_id)
    if download is None:
        raise HTTPException(status_code=404, detail="Sources not found")
    import json

    data = json.loads((download.get("body") or b"{}").decode("utf-8"))
    return {"query_run_id": query_run_id, "citations": data.get("citations") or []}


@router.get("/chat/query-runs/{query_run_id}/context")
@limiter.limit("60/minute")
async def get_query_run_context(
    request: Request,
    query_run_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    retrieval = getattr(svc, "retrieval_service", None)
    if retrieval is None or not hasattr(retrieval, "get_query_context_download"):
        raise HTTPException(status_code=404, detail="Context not found")
    download = retrieval.get_query_context_download(query_run_id)
    if download is None:
        raise HTTPException(status_code=404, detail="Context not found")
    import json

    return json.loads((download.get("body") or b"{}").decode("utf-8"))


@router.get("/chat/sources/{query_run_id}/{source_id}/download")
@limiter.limit("60/minute")
async def chat_source_download(
    request: Request,
    query_run_id: str,
    source_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    """Citation/evidence export — nem az eredeti feltöltött dokumentum letöltése."""
    if not hasattr(svc, "download_answer_source"):
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        download = svc.download_answer_source(
            query_run_id=query_run_id,
            source_id=source_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except ChatPermissionDenied:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if download is None:
        raise HTTPException(status_code=404, detail="Source not found")
    filename = str(download.get("filename") or f"aiplaza-context-{source_id[:8]}.txt")
    return Response(
        content=download.get("body") or b"",
        media_type=str(download.get("content_type") or "text/plain; charset=utf-8"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/chat/context/{query_run_id}/download")
@limiter.limit("60/minute")
async def chat_context_download(
    request: Request,
    query_run_id: str,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    if not hasattr(svc, "download_answer_context"):
        raise HTTPException(status_code=404, detail="Context not found")
    try:
        download = svc.download_answer_context(
            query_run_id=query_run_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
    except ChatPermissionDenied:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if download is None:
        raise HTTPException(status_code=404, detail="Context not found")
    filename = str(download.get("filename") or f"aiplaza-llm-context-{query_run_id[:8]}.txt")
    return Response(
        content=download.get("body") or b"",
        media_type=str(download.get("content_type") or "text/plain; charset=utf-8"),
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket):
    """
    WebSocket chat: token HttpOnly cookie (ws_token). Query param NINCS (biztonság: ne kerüljön logokba).
    Opcionálisan tenant=yyy query. Üzenet: {"question": "..."}; válasz: {"chunk": "..."}, majd {"done": true}.
    """
    token = websocket.cookies.get("ws_token")
    if not _ws_enabled():
        await websocket.close(code=4403)
        return
    tenant_slug = websocket.query_params.get("tenant") or None
    if not tenant_slug:
        tenant_slug = str(getattr(settings, "single_tenant_slug", "") or "").strip() or None
    user = await validate_ws_token(token, tenant_slug)
    if not user or not getattr(user, "is_active", True):
        await websocket.close(code=4401)
        return
    remote_ip = websocket.client.host if websocket.client else None
    tenant_repo = get_tenant_repository()
    tenant = tenant_repo.get_by_slug(tenant_slug) if tenant_slug else None
    if tenant is None:
        await websocket.close(code=4404)
        return
    acquired, acquire_reason, conn_reservation = _ws_try_acquire_connection(
        tenant_slug=tenant_slug,
        user_id=getattr(user, "id", None),
    )
    if not acquired:
        increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "conn_limit"})
        await websocket.close(code=4429, reason=acquire_reason[:120] if acquire_reason else "")
        return
    await websocket.accept()
    svc = get_chat_service()
    usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
    limits = _tenant_chat_limits(tenant)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=_ws_idle_timeout_sec())
            except asyncio.TimeoutError:
                await websocket.send_json({"error": "Idle timeout"})
                await websocket.close(code=4408)
                return
            if len(data or "") > _ws_max_message_chars():
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "payload_too_large"})
                await websocket.send_json({"error": "Message too large"})
                continue
            if not _ws_allow_message(tenant_slug=tenant_slug, user_id=getattr(user, "id", None), remote_ip=remote_ip):
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "rate_limit"})
                await websocket.send_json({"error": "Too many websocket messages"})
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "invalid_json"})
                await websocket.send_json({"error": "Invalid JSON"})
                continue
            question = msg.get("question") if isinstance(msg, dict) else None
            kb_uuid = str(msg.get("kb_uuid") or "").strip() if isinstance(msg, dict) else ""
            if not question or not isinstance(question, str):
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "missing_question"})
                await websocket.send_json({"error": "Missing or invalid question"})
                continue
            question = question.strip()
            if not question:
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "empty_question"})
                await websocket.send_json({"error": "Empty question"})
                continue
            if len(question) > _ws_max_message_chars() or len(question) > int(limits["max_question_chars"]):
                increment_metric("ws.msg_reject_total", 1.0, tags={"reason": "question_too_large"})
                await websocket.send_json({"error": "Question too large"})
                continue
            try:
                result = await handle_ws_chat_message(
                    svc=svc,
                    usage_service=usage_service,
                    tenant=tenant,
                    user=user,
                    question=question,
                    kb_uuid=kb_uuid or None,
                    limits=limits,
                )
                if isinstance(result, dict):
                    await websocket.send_json({"error": result.get("error") or "Chat unavailable"})
                    if result.get("close_code"):
                        await websocket.close(code=int(result["close_code"]), reason=str(result.get("close_reason") or ""))
                        return
                    continue
                async for event in result:
                    await websocket.send_json(event)
            except PiiDepersonalizationUnavailableError as exc:
                await websocket.send_json({"error": str(exc)})
                await websocket.close(code=1013, reason="PII depersonalization unavailable")
                return
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        _ws_release_connection(conn_reservation)
