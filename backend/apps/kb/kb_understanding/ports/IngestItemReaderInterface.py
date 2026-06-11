from __future__ import annotations

# backend/apps/kb/kb_understanding/ports/IngestItemReaderInterface.py
# Feladat: Ingest item olvasási szerződés — a kb_ingest oldali adapter a kompozíciós
# gyökéren keresztül kerül regisztrálásra (nincs közvetlen kereszt-import).
# Sárközi Mihály - 2026.06.11

from typing import Protocol

from apps.kb.shared.contracts import IngestItemSnapshot


class IngestItemReaderInterface(Protocol):
    def get_item_snapshot(self, item_id: str) -> IngestItemSnapshot | None: ...


__all__ = ["IngestItemReaderInterface"]
