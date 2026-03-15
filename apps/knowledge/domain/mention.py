from __future__ import annotations

from pydantic import BaseModel


class Mention(BaseModel):
    id: int | None = None
    sentence_id: int
    surface_form: str
    mention_type: str
    grammatical_role: str | None = None
    sentence_local_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    resolved_entity_id: int | None = None
    resolution_confidence: float = 0.0
    is_implicit_subject: bool = False
