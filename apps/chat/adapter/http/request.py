# apps/chat/adapter/http/request.py
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Non-empty question text")
    kb_uuid: str | None = Field(default=None, description="Opcionális tudástár UUID scope")
    debug: bool = Field(default=False, description="Debug context visszaadása")
