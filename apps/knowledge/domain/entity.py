from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: int | None = None
    kb_id: int
    source_point_id: str | None = None
    canonical_name: str
    canonical_key: str | None = None
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
