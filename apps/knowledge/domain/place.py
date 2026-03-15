from __future__ import annotations

from pydantic import BaseModel


class Place(BaseModel):
    """Feloldott place dimenzió.

    A `normalized_key` a retrieval-kompatibilis canonical kulcs.
    A `parent_place_id` a hierarchy szervező tengelye, amelyet query resolve,
    place match és context build is használhat.
    """
    id: int | None = None
    kb_id: int
    canonical_name: str
    normalized_key: str
    place_type: str | None = None
    country_code: str | None = None
    parent_place_id: int | None = None
    confidence: float = 0.0
