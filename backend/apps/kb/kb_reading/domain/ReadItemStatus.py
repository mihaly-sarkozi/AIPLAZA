from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadItemStatus.py
# Feladat: Elem lehetséges állapotai.
# Sárközi Mihály - 2026.06.07

from enum import Enum


class ReadItemStatus(str, Enum):
    """Elem lehetséges állapotértékei."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


__all__ = ["ReadItemStatus"]
