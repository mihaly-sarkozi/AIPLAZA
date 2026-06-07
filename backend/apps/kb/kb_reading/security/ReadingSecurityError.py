from __future__ import annotations

# backend/apps/kb/kb_reading/security/ReadingSecurityError.py
# Feladat: Fájl biztonsági ellenőrzés hiba.
# Sárközi Mihály - 2026.06.07
class ReadingSecurityError(ValueError):
    """Fájl biztonsági ellenőrzés hiba."""
    pass

__all__ = ['ReadingSecurityError']
