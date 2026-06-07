from __future__ import annotations

from pydantic import BaseModel

from apps.kb.kb_reading.domain.ReadingErrorCode import ReadingErrorCode


class ReadFileEstimateItemResponse(BaseModel):
    filename: str
    mime_type: str | None = None
    size_bytes: int = 0
    char_count: int = 0
    within_quota: bool = True
    error_code: ReadingErrorCode | None = None
    error_message: str | None = None


__all__ = ["ReadFileEstimateItemResponse"]
