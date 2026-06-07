from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadRunStatus.py
# Feladat: Futás lehetséges állapotai.
# Sárközi Mihály - 2026.06.07

from enum import Enum


class ReadRunStatus(str, Enum):
    """Futás lehetséges állapotértékei."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


__all__ = ["ReadRunStatus"]
