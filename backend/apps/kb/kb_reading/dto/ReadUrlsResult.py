from __future__ import annotations

# backend/apps/kb/kb_reading/dto/ReadUrlsResult.py
# Feladat: ReadUrlsResult adatszerkezet.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass

from apps.kb.kb_reading.domain.ReadRunStatus import ReadRunStatus


@dataclass(frozen=True)
class ReadUrlsResult:
    """Hálózati cím beolvasás eredménye."""

    read_run_id: str
    status: ReadRunStatus
    accepted_count: int
    failed_count: int
    rejected_count: int
    duplicate_count: int
    item_ids: list[str]


__all__ = ["ReadUrlsResult"]
