# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
import inspect
import json
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from apps.chat.dependencies import get_chat_service
from core.kernel.config.config_loader import settings
from core.di import RequiredTenantContextDep, get_service
from core.platform.service_keys import PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.security.rate_limit import limiter
from core.capabilities.users.dto import User
from core.platform.auth.auth_dependencies import get_current_user, validate_ws_token
from core.kernel.security.cookie_policy import set_ws_token_cookie

from apps.chat.router.chat_requests import AskRequest, ChatFeedbackRequest
from apps.chat.router.chat_response import AskResponse

router = APIRouter()

@router.get("/chat/ws-token")
async def chat_ws_token(
    request: Request,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
):
    """
    WebSocket auth: Bearer token → ws_token HttpOnly cookie (rövid életű).
    A frontend ezt hívja credentials-szel; utána a /chat/ws kapcsolat a cookie-t küldi (token nem kerül URL-be/logokba).
    """
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
    try:
        usage_service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
        allowed, reason = usage_service.can_consume_question(tenant)
        if not allowed:
            raise HTTPException(status_code=402, detail=reason)
        if hasattr(svc, "chat_with_sources"):
            chat_with_sources = getattr(svc, "chat_with_sources")
            if inspect.iscoroutinefunction(chat_with_sources):
                try:
                    payload = await chat_with_sources(
                        req.question,
                        user_id=current_user.id,
                        user_role=current_user.role,
                        kb_uuid=req.kb_uuid,
                        debug=req.debug,
                        conversation_history=req.conversation_history,
                    )
                except TypeError:
                    # Backward compatibility régi ChatService mock/signature esetére.
                    try:
                        payload = await chat_with_sources(
                            req.question,
                            user_id=current_user.id,
                            user_role=current_user.role,
                            kb_uuid=req.kb_uuid,
                            debug=req.debug,
                        )
                    except TypeError:
                        payload = await chat_with_sources(req.question)
                usage_service.record_question(tenant, current_user.id)
                return AskResponse(
                    answer=str(payload.get("answer") or ""),
                    query_run_id=payload.get("query_run_id") or None,
                    sources=payload.get("sources") or [],
                    debug=(payload.get("debug") if req.debug else None),
                    answer_mode=str(payload.get("answer_mode") or "no_answer"),
                    answer_source=str(payload.get("answer_source") or "none"),
                    confidence=float(payload.get("confidence") or 0.0),
                    evidence=payload.get("evidence") or [],
                    cited_claim_ids=payload.get("cited_claim_ids") or [],
                    cited_sentence_ids=payload.get("cited_sentence_ids") or [],
                    cited_source_ids=payload.get("cited_source_ids") or [],
                    query_profile=payload.get("query_profile") or {},
                    matched_chunks=payload.get("matched_chunks") or [],
                    claims=payload.get("claims") or [],
                    context_blocks=payload.get("context_blocks") or [],
                )
        try:
            answer = await svc.chat(
                req.question,
                user_id=current_user.id,
                user_role=current_user.role,
                kb_uuid=req.kb_uuid,
                debug=req.debug,
                conversation_history=req.conversation_history,
            )
        except TypeError:
            # Backward compatibility régi ChatService mock/signature esetére.
            try:
                answer = await svc.chat(
                    req.question,
                    user_id=current_user.id,
                    user_role=current_user.role,
                    kb_uuid=req.kb_uuid,
                    debug=req.debug,
                )
            except TypeError:
                answer = await svc.chat(req.question)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    usage_service.record_question(tenant, current_user.id)
    return AskResponse(answer=answer, sources=[], debug=None, answer_source="llm_fallback" if answer else "none")


@router.post("/chat/feedback")
@limiter.limit("60/minute")
async def chat_feedback(
    request: Request,
    req: ChatFeedbackRequest,
    tenant: RequiredTenantContextDep,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    if not hasattr(svc, "capture_retrieval_feedback"):
        return {"status": "skipped", "reason": "feedback_service_not_available"}
    return svc.capture_retrieval_feedback(
        trace_id=req.trace_id,
        helpful=req.helpful,
        note=req.note,
    )


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
    if not hasattr(svc, "download_answer_source"):
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        download = svc.download_answer_source(
            query_run_id=query_run_id,
            source_id=source_id,
            user_id=current_user.id,
            user_role=current_user.role,
        )
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
    tenant_slug = websocket.query_params.get("tenant") or None
    user = await validate_ws_token(token, tenant_slug)
    if not user or not getattr(user, "is_active", True):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    svc = get_chat_service()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue
            question = msg.get("question") if isinstance(msg, dict) else None
            if not question or not isinstance(question, str):
                await websocket.send_json({"error": "Missing or invalid question"})
                continue
            question = question.strip()
            if not question:
                await websocket.send_json({"error": "Empty question"})
                continue
            try:
                async for chunk in svc.chat_stream(question, user_id=user.id, user_role=user.role):
                    await websocket.send_json({"chunk": chunk})
            except TypeError:
                async for chunk in svc.chat_stream(question):
                    await websocket.send_json({"chunk": chunk})
            await websocket.send_json({"done": True})
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
