from __future__ import annotations

# backend/apps/kb/kb_reading/service/_PreparedFile.py
# Feladat: _PreparedFile adatszerkezet.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass


@dataclass
class _PreparedFile:
    """Előkészített fájl adatok a beolvasáshoz."""

    filename: str
    mime_type: str | None
    raw: bytes
    content_hash: str
    idempotency_key: str
    title: str
    estimated_char_count: int


__all__ = ["_PreparedFile"]
