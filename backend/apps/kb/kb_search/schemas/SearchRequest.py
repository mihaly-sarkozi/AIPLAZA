from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    knowledge_base_id: str
    question: str = Field(min_length=1)
