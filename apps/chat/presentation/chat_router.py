# apps/chat/presentation/chat_router.py
from fastapi import APIRouter, Depends, Request
from apps.core.middleware.rate_limit_middleware import limiter
from apps.core.security.auth_dependencies import get_current_user
from apps.users.domain.user import User

from apps.chat.adapter.http.request import AskRequest
from apps.chat.adapter.http.response import AskResponse

from apps.core.di import get_chat_service, set_tenant_context_from_request

router = APIRouter(dependencies=[Depends(set_tenant_context_from_request)])

@router.post("/chat", response_model=AskResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    svc=Depends(get_chat_service),
):
    answer = await svc.chat(req.question)  # ✅ most már await kell
    return AskResponse(answer=answer)