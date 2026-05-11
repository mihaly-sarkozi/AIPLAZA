# Ez a fájl az adott modul HTTP útvonalait és kérés-válasz illesztését tartalmazza.
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KBOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    name: str
    description: Optional[str]
    qdrant_collection_name: str
    personal_data_mode: str = "no_personal_data"
    personal_data_sensitivity: str = "medium"
    pii_depersonalization_enabled: bool = True
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    status: str = "active"
    can_train: Optional[bool] = None  # aktuális user taníthatja-e (listánál kitöltve)
    has_training: bool = False  # van-e legalább egy tanítási/ingest bejegyzés ebben a tudástárban
    storage_metrics: dict[str, int] = Field(default_factory=dict)


class KBPermissionOut(BaseModel):
    user_id: int
    email: str
    name: Optional[str]
    permission: str
    role: str
