from __future__ import annotations

from pydantic import BaseModel, Field


class ReadUrlItem(BaseModel):
    url: str = Field(..., min_length=1)
    title: str | None = None


__all__ = ["ReadUrlItem"]
