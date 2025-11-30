# apps/chat/adapter/http/response.py
from pydantic import BaseModel

class AskResponse(BaseModel):
    answer: str
