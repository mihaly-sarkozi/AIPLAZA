from __future__ import annotations

# backend/apps/kb/kb_reading/dto/ReadRunDetailResponse.py
# Feladat: ReadRunDetailResponse válasz séma.
# Sárközi Mihály - 2026.06.07
from pydantic import BaseModel, Field
from apps.kb.kb_reading.dto.ReadEventResponse import ReadEventResponse
from apps.kb.kb_reading.dto.ReadItemResponse import ReadItemResponse
from apps.kb.kb_reading.dto.ReadRunResponse import ReadRunResponse

class ReadRunDetailResponse(BaseModel):
    """Válasz séma a futás részletes adataihoz."""
    run: ReadRunResponse
    items: list[ReadItemResponse] = Field(default_factory=list)
    events: list[ReadEventResponse] = Field(default_factory=list)

__all__ = ['ReadRunDetailResponse']
