from __future__ import annotations

# backend/apps/kb/kb_understanding/enums/UnderstandingStatus.py
# Feladat: A megértési feldolgozás kanonikus státuszkészlete (job / item szint).
# Sárközi Mihály - 2026.06.11

from enum import Enum


class UnderstandingStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    STRUCTURING = "structuring"
    CHUNKING = "chunking"
    EXTRACTING_ENTITIES = "extracting_entities"
    ENRICHING = "enriching"
    EMBEDDING = "embedding"
    BUILDING_RELATIONSHIPS = "building_relationships"
    SCORING = "scoring"
    VALIDATING = "validating"
    READY_FOR_INDEXING = "ready_for_indexing"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYABLE = "retryable"


# Lezárt (nem futó) állapotok — retry / új job indítás engedélyezéséhez.
TERMINAL_STATUSES = frozenset(
    {
        UnderstandingStatus.READY_FOR_INDEXING,
        UnderstandingStatus.PARTIAL,
        UnderstandingStatus.FAILED,
        UnderstandingStatus.RETRYABLE,
    }
)


__all__ = ["TERMINAL_STATUSES", "UnderstandingStatus"]
