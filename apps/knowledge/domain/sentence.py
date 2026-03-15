from __future__ import annotations

from pydantic import BaseModel


class Sentence(BaseModel):
    id: int | None = None
    kb_id: int
    source_point_id: str
    sentence_order: int
    text: str
    sanitized_text: str
    token_count: int = 0
    qdrant_point_id: str | None = None
