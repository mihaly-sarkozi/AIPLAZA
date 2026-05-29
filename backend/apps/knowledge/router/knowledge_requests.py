# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from typing import List, Optional

from pydantic import BaseModel, Field


class KBCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    permissions: Optional[List[dict]] = None  # [ {"user_id": int, "permission": "use"|"train"|"none"} ]

class KBUpdate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    personal_data_mode: Optional[str] = Field(
        default=None,
        description="no_personal_data | with_confirmation | allowed_not_to_ai | no_pii_filter",
    )
    pii_depersonalization_enabled: Optional[bool] = None
    public_enabled: Optional[bool] = None

class KBDelete(BaseModel):
    confirm_name: str


class KBPermissionItem(BaseModel):
    user_id: int
    permission: str


class KBPermissionsUpdate(BaseModel):
    permissions: List[KBPermissionItem]


class KBBatchPermissionsRequest(BaseModel):
    uuids: List[str] = Field(default_factory=list, max_length=100)
