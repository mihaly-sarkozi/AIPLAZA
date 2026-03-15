# apps/chat/presentation/chat_router.py
import inspect
import json
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from config.settings import settings
from apps.core.middleware.rate_limit_middleware import limiter
from apps.core.security.auth_dependencies import get_current_user, validate_ws_token
from apps.core.security.cookie_policy import set_ws_token_cookie
from apps.users.domain.user import User

from apps.chat.adapter.http.request import AskRequest
from apps.chat.adapter.http.response import AskResponse

from apps.core.di import get_chat_service, set_tenant_context_from_request

router = APIRouter()

@router.get("/chat/ws-token", dependencies=[Depends(set_tenant_context_from_request)])
async def chat_ws_token(request: Request, current_user: User = Depends(get_current_user)):
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


@router.post(
    "/chat",
    response_model=AskResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(set_tenant_context_from_request)],
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    try:
        if hasattr(svc, "chat_with_sources"):
            chat_with_sources = getattr(svc, "chat_with_sources")
            if inspect.iscoroutinefunction(chat_with_sources):
                payload = await chat_with_sources(
                    req.question,
                    user_id=current_user.id,
                    user_role=current_user.role,
                    kb_uuid=req.kb_uuid,
                    debug=req.debug,
                )
                return AskResponse(
                    answer=str(payload.get("answer") or ""),
                    sources=payload.get("sources") or [],
                    debug=(payload.get("debug") if req.debug else None),
                )
        try:
            answer = await svc.chat(
                req.question,
                user_id=current_user.id,
                user_role=current_user.role,
                kb_uuid=req.kb_uuid,
                debug=req.debug,
            )
        except TypeError:
            # Backward compatibility régi ChatService mock/signature esetére.
            answer = await svc.chat(req.question)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return AskResponse(answer=answer, sources=[], debug=None)


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