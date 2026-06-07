from __future__ import annotations

# backend/apps/kb/kb_reading/security/UrlFetchResult.py
# Feladat: Letöltés eredménye.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass


@dataclass(frozen=True)
class UrlFetchResult:
    """Letöltés eredménye metaadatokkal."""

    origin_url: str
    final_url: str
    status_code: int
    content_type: str | None
    body: bytes
    size_bytes: int


__all__ = ["UrlFetchResult"]
