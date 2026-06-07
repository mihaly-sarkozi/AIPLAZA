from __future__ import annotations

from pydantic import BaseModel


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str


__all__ = ["KnowledgeBaseResponse"]
