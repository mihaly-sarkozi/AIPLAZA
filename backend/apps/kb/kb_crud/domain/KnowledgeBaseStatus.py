from __future__ import annotations

from enum import Enum


class KnowledgeBaseStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


__all__ = ["KnowledgeBaseStatus"]
