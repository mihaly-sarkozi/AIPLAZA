from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeBase:
    id: str
    name: str
    description: str | None
    status: str


__all__ = ["KnowledgeBase"]
