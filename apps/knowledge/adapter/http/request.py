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
    personal_data_mode: str = Field(..., description="no_personal_data | with_confirmation | allowed_not_to_ai | no_pii_filter")

class KBDelete(BaseModel):
    confirm_name: str

class KBPermissionItem(BaseModel):
    user_id: int
    permission: str  # "use" | "train" | "none"

class KBPermissionsUpdate(BaseModel):
    permissions: List[KBPermissionItem]


class KBBatchPermissionsRequest(BaseModel):
    uuids: List[str] = Field(default_factory=list, max_length=100)


class KBDsarSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=256)
    limit: int = Field(default=100, ge=1, le=1000)
    scan_limit: int = Field(default=2000, ge=10, le=10000)


class KBDsarDeleteRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=256)
    limit: int = Field(default=100, ge=1, le=1000)
    scan_limit: int = Field(default=5000, ge=10, le=20000)
    dry_run: bool = False

class PiiDecisionItem(BaseModel):
    index: int
    decision: str  # "delete" | "mask" | "keep"


class KBTrainRequest(BaseModel):
    title: Optional[str] = ""
    content: str
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    confirm_pii: bool = False
    pii_review_decision: Optional[str] = None  # mask_all | keep_role_based_emails | reject_upload | continue_sanitized
    pii_decisions: Optional[List[dict]] = None  # [{"index": int, "decision": "delete"|"mask"|"keep"}]