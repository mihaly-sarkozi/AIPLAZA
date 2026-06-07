from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadEvent.py
# Feladat: Naplózott esemény a beolvasás során.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ReadEvent:
    """Naplózott esemény a beolvasás során."""
    id: str
    read_run_id: str
    read_item_id: str | None
    event_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


__all__ = ["ReadEvent"]
