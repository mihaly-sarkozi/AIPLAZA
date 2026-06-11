from __future__ import annotations

# backend/apps/kb/kb_ingest/ports/ReadableUpload.py
# Feladat: Feltöltött fájl olvasható felülete a becsléshez.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

from typing import Protocol


class ReadableUpload(Protocol):
    """Feltöltött fájl olvasható felülete a becsléshez."""
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes: ...


__all__ = ["ReadableUpload"]
