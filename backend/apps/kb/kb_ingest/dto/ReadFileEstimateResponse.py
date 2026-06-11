from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/ReadFileEstimateResponse.py
# Feladat: Fájl becslés összesített eredménye.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel, Field

from apps.kb.kb_ingest.dto.ReadFileEstimateItemResponse import ReadFileEstimateItemResponse


class ReadFileEstimateResponse(BaseModel):
    file_count: int
    total_size_bytes: int = 0
    total_char_count: int = 0
    can_start: bool = True
    reason: str | None = None
    is_estimate: bool = True
    items: list[ReadFileEstimateItemResponse] = Field(default_factory=list)


__all__ = ["ReadFileEstimateResponse"]
