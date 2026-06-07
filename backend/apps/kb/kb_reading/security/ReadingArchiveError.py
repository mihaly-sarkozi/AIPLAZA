from __future__ import annotations

# backend/apps/kb/kb_reading/security/ReadingArchiveError.py
# Feladat: Tömörített csomag ellenőrzés hiba.
# Sárközi Mihály - 2026.06.07
class ReadingArchiveError(ValueError):
    """Tömörített csomag ellenőrzés hiba."""
    pass

__all__ = ['ReadingArchiveError']
