from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadRun.py
# Feladat: Beolvasási futás modellje: köteg állapota és számlálók.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from apps.kb.kb_reading.domain.ReadRunStatus import ReadRunStatus


@dataclass
class ReadRun:
    """Egy beolvasási futás adatai és állapota."""
    id: str
    tenant: str
    knowledge_base_id: str
    input_channel: str
    status: ReadRunStatus
    batch_size: int
    queued_count: int
    failed_count: int
    rejected_count: int
    duplicate_count: int
    created_by: int
    created_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ReadRun"]
