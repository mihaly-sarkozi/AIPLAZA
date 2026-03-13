from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class KBOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    name: str
    description: Optional[str]
    qdrant_collection_name: str
    personal_data_mode: str = "no_personal_data"
    personal_data_sensitivity: str = "medium"
    created_at: datetime
    updated_at: datetime
    can_train: Optional[bool] = None  # aktuális user taníthatja-e (listánál kitöltve)


class KBPermissionOut(BaseModel):
    user_id: int
    email: str
    name: Optional[str]
    permission: str  # "use" | "train" | "none"
    role: str  # "user" | "admin" | "owner"
