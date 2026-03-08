# apps/knowledge/adapter/http/request.py
from pydantic import BaseModel, Field
from typing import Optional, List

class KBCreate(BaseModel):
    name: str = Field(..., max_length=20)
    description: Optional[str] = None
    permissions: Optional[List[dict]] = None  # [ {"user_id": int, "permission": "use"|"train"|"none"} ]

class KBUpdate(BaseModel):
    name: str = Field(..., max_length=20)
    description: Optional[str] = None

class KBDelete(BaseModel):
    confirm_name: str

class KBPermissionItem(BaseModel):
    user_id: int
    permission: str  # "use" | "train" | "none"

class KBPermissionsUpdate(BaseModel):
    permissions: List[KBPermissionItem]

class KBTrainRequest(BaseModel):
    title: str
    content: str