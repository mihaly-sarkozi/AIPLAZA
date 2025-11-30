# apps/chat/adapter/http/request.py
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str
