from __future__ import annotations

# backend/apps/kb/kb_reading/security/UrlTarget.py
# Feladat: Ellenőrzött hálózati cél.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass
from urllib.parse import ParseResult


@dataclass(frozen=True)
class UrlTarget:
    """Ellenőrzött hálózati cél adatai."""

    url: str
    parsed: ParseResult
    addresses: tuple[str, ...]


__all__ = ["UrlTarget"]
