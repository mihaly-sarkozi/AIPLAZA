from __future__ import annotations

# backend/apps/kb/kb_crud/ports/ContentCleanupInterface.py
# Feladat: Tudástár tartalom törlésének (DB + vektor index + object storage) szerződése.
# Sárközi Mihály - 2026.06.11

from typing import Protocol


class ContentCleanupInterface(Protocol):
    def clear_contents(self, kb_uuid: str, *, confirm_name: str | None = None) -> dict[str, int]:
        """Kiüríti a tudástár teljes tartalmát; a törölt rekordszámokat adja vissza."""
        ...


__all__ = ["ContentCleanupInterface"]
