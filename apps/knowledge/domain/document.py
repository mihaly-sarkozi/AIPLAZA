from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class Document(BaseModel):
    """Forrásdokumentum reprezentáció a training log szintjén."""

    kb_id: int
    source_point_id: str
    title: str
    sanitized_content: str
    created_at: datetime | None = None
