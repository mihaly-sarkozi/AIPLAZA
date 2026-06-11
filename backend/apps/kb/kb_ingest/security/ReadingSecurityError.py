from __future__ import annotations

# backend/apps/kb/kb_ingest/security/ReadingSecurityError.py
# Feladat: Fájl biztonsági ellenőrzés hiba.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11
class ReadingSecurityError(ValueError):
    """Fájl biztonsági ellenőrzés hiba."""
    pass

__all__ = ['ReadingSecurityError']
