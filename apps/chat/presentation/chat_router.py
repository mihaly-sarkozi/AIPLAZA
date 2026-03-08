# apps/chat/presentation/chat_router.py
import json
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from apps.core.middleware.rate_limit_middleware import limiter
from apps.core.security.auth_dependencies import get_current_user, validate_ws_token
from apps.users.domain.user import User

from apps.chat.adapter.http.request import AskRequest
from apps.chat.adapter.http.response import AskResponse

from apps.core.di import get_chat_service, set_tenant_context_from_request

router = APIRouter()

@router.post("/chat", response_model=AskResponse, dependencies=[Depends(set_tenant_context_from_request)])
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    answer = await svc.chat(req.question)  # ✅ most már await kell
    return AskResponse(answer=answer)


@router.websocket("/chat/ws")
async def chat_ws(websocket: WebSocket):
    """
    WebSocket chat: token a query param (token=xxx), opcionálisan tenant=yyy.
    Üzenet formátum: {"question": "..."}. A szerver streameli a választ: {"chunk": "..."}, majd {"done": true}.
    """
    token = websocket.query_params.get("token")
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