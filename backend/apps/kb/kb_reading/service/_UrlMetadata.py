from __future__ import annotations

# backend/apps/kb/kb_reading/service/_UrlMetadata.py
# Feladat: _UrlMetadata adatszerkezet.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass


@dataclass(frozen=True)
class _UrlMetadata:
    """Belső metaadatok egy hálózati cím elemhez."""

    same_url_seen_before: bool
    previous_item_id: str | None
    content_changed: bool


__all__ = ["_UrlMetadata"]
