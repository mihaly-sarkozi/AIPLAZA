from __future__ import annotations

# backend/apps/kb/kb_reading/dto/event.py
# Feladat: Esemény séma a válaszokban.
# Sárközi Mihály - 2026.06.07

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReadEventResponse(BaseModel):
    """Adatátviteli séma a kérés vagy válasz mezőihez."""
    id: str
    read_run_id: str
    read_item_id: str | None = None
    event_type: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


__all__ = ["ReadEventResponse"]
