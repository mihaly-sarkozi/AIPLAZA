from __future__ import annotations

# backend/apps/kb/kb_crud/domain/KnowledgeBaseStatus.py
# Feladat: Tudástár életciklus státusz enum.
# Sárközi Mihály - 2026.06.07

from enum import Enum


class KnowledgeBaseStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


__all__ = ["KnowledgeBaseStatus"]
