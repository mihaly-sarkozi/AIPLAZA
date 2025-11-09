# apps/api/schemas/chat.py
from pydantic import BaseModel

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
