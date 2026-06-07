from __future__ import annotations

# backend/apps/kb/kb_reading/security/ReadingUrlSecurityError.py
# Feladat: Hálózati cím biztonsági hiba.
# Sárközi Mihály - 2026.06.07
from apps.kb.shared.errors import KbValidationError

class ReadingUrlSecurityError(KbValidationError):
    """Hálózati cím biztonsági hiba."""
    def __init__(self, code: str, message: str) -> None:
        """Összeállítja a szükséges függőségeket."""
        super().__init__(message)
        self.code = str(code or "URL_SECURITY_REJECTED").strip() or "URL_SECURITY_REJECTED"

__all__ = ['ReadingUrlSecurityError']
