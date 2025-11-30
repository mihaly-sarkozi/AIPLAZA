from __future__ import annotations

from pydantic import BaseModel
from datetime import datetime

class KnowledgeBase(BaseModel):
    id: int | None
    uuid: str
    name: str
    description: str | None
    qdrant_collection_name: str
    created_at: datetime | None
    updated_at: datetime | None
