from __future__ import annotations

from pydantic import BaseModel, Field


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None


__all__ = ["CreateKnowledgeBaseRequest"]
