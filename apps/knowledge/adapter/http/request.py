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
    personal_data_mode: str = Field(..., description="no_personal_data | with_confirmation | allowed_not_to_ai")
    personal_data_sensitivity: str = Field(..., description="weak | medium | strong")

class KBDelete(BaseModel):
    confirm_name: str

class KBPermissionItem(BaseModel):
    user_id: int
    permission: str  # "use" | "train" | "none"

class KBPermissionsUpdate(BaseModel):
    permissions: List[KBPermissionItem]

class KBTrainRequest(BaseModel):
    title: Optional[str] = ""
    content: str
    confirm_pii: bool = False
    pii_review_decision: Optional[str] = None  # mask_all | keep_role_based_emails | reject_upload | continue_sanitized