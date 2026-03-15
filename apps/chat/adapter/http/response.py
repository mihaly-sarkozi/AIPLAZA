# apps/chat/adapter/http/response.py
from pydantic import BaseModel, Field


class ChatSourceItem(BaseModel):
    kb_uuid: str
    point_id: str
    title: str = ""
    snippet: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[ChatSourceItem] = Field(default_factory=list)
