from __future__ import annotations

from pydantic import BaseModel, Field

from apps.kb.kb_reading.dto.ReadUrlItem import ReadUrlItem


class ReadUrlRequest(BaseModel):
    items: list[ReadUrlItem] = Field(..., min_length=1)


__all__ = ["ReadUrlRequest"]
