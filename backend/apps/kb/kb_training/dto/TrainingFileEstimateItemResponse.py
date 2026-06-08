from __future__ import annotations

from pydantic import BaseModel


class TrainingFileEstimateItemResponse(BaseModel):
    filename: str
    mime_type: str | None = None
    char_count: int = 0
    storage_bytes: int = 0
    error_code: str | None = None
    error_message: str | None = None


__all__ = ["TrainingFileEstimateItemResponse"]
