# Ez a fájl a(z) kb modul backend logikáját tartalmazza.
from __future__ import annotations

from pydantic import BaseModel
from datetime import datetime

class KnowledgeBase(BaseModel):
    id: int | None
    uuid: str
    name: str
    description: str | None
    qdrant_collection_name: str
    personal_data_mode: str = "no_personal_data"   # no_personal_data | with_confirmation | allowed_not_to_ai
    personal_data_sensitivity: str = "medium"       # weak | medium | strong
    pii_depersonalization_enabled: bool = True
    created_at: datetime | None
    updated_at: datetime | None
    deleted_at: datetime | None = None
    deleted_display_name: str | None = None
    deleted_training_char_count: int = 0
