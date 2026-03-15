from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from apps.knowledge.domain.sentence import Sentence  # visszafelé kompatibilis export


class StructuralChunk(BaseModel):
    id: int | None = None
    kb_id: int
    source_point_id: str
    chunk_order: int
    text: str
    sentence_ids: list[int] = Field(default_factory=list)
    assertion_ids: list[int] = Field(default_factory=list)
    entity_ids: list[int] = Field(default_factory=list)
    token_count: int = 0
    time_from: datetime | None = None
    time_to: datetime | None = None
    place_keys: list[str] = Field(default_factory=list)
    qdrant_point_id: str | None = None
