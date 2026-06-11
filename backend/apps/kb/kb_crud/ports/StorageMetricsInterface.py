from __future__ import annotations

# backend/apps/kb/kb_crud/ports/StorageMetricsInterface.py
# Feladat: Tudástár tárhely metrikák (file/db/qdrant bytes, pontok, karakterszám) szerződése.
# Sárközi Mihály - 2026.06.11

from typing import Protocol

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase


class StorageMetricsInterface(Protocol):
    def metrics_for(self, kb: KnowledgeBase) -> dict[str, int]:
        """A tudástár tárhely metrikái (üres dict, ha nem elérhető)."""
        ...


__all__ = ["StorageMetricsInterface"]
