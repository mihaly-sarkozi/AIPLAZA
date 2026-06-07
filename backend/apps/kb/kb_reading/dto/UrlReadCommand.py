from __future__ import annotations

# backend/apps/kb/kb_reading/dto/UrlReadCommand.py
# Feladat: UrlReadCommand adatszerkezet.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass

from apps.kb.kb_reading.dto.ReadUrlRequest import ReadUrlRequest


@dataclass(frozen=True)
class UrlReadCommand:
    """Hálózati cím beolvasás parancs a bérlővel és címekkel."""

    tenant: str
    knowledge_base_id: str
    created_by: int
    request: ReadUrlRequest


__all__ = ["UrlReadCommand"]
