# apps/api/routers/chat.py
from fastapi import APIRouter, Depends
from apps.api.schemas.chat import AskRequest, AskResponse
from apps.api.di import get_chat_service

from apps.api.middleware.rate_limit import limiter
router = APIRouter()

@router.post("/chat/ask", response_model=AskResponse)
@limiter.limit("30/minute")
async def chat(req: AskRequest, svc = Depends(get_chat_service)):
    answer = await svc.chat(req.question)
    return AskResponse(answer=answer)