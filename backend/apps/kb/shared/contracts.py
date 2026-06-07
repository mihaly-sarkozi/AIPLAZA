from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaterialRef:
    material_id: str
    knowledge_base_id: str
    raw_ref: str
    content_type: str


@dataclass
class SearchContextItem:
    chunk_id: str
    source_id: str | None
    text: str
    score: float


__all__ = ["MaterialRef", "SearchContextItem"]
