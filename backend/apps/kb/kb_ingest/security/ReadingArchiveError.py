from __future__ import annotations

# backend/apps/kb/kb_ingest/security/ReadingArchiveError.py
# Feladat: Tömörített csomag ellenőrzés hiba.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11
class ReadingArchiveError(ValueError):
    """Tömörített csomag ellenőrzés hiba."""
    pass

__all__ = ['ReadingArchiveError']
