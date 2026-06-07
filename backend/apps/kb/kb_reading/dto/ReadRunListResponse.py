from __future__ import annotations

from pydantic import BaseModel, Field

from apps.kb.kb_reading.dto.ReadRunResponse import ReadRunResponse


class ReadRunListResponse(BaseModel):
    items: list[ReadRunResponse] = Field(default_factory=list)
    total: int = 0


__all__ = ["ReadRunListResponse"]
