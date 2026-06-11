from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/ReadFileEstimateItemResponse.py
# Feladat: Egy fájl becslés eredménye.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel

from apps.kb.kb_ingest.enums.ReadingErrorCode import ReadingErrorCode


class ReadFileEstimateItemResponse(BaseModel):
    filename: str
    mime_type: str | None = None
    size_bytes: int = 0
    char_count: int = 0
    within_quota: bool = True
    error_code: ReadingErrorCode | None = None
    error_message: str | None = None


__all__ = ["ReadFileEstimateItemResponse"]
