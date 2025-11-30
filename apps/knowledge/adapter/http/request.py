# apps/knowledge/adapter/http/request.py
from pydantic import BaseModel, Field
from typing import Optional

class KBCreate(BaseModel):
    name: str = Field(..., max_length=20)
    description: Optional[str] = None

class KBUpdate(BaseModel):
    name: str = Field(..., max_length=20)
    description: Optional[str] = None

class KBDelete(BaseModel):
    confirm_name: str

class KBTrainRequest(BaseModel):
    title: str
    content: str