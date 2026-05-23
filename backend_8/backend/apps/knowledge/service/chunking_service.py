# backend/apps/knowledge/service/chunking_service.py
# Feladat: Knowledge text chunking adapter. A chunk builder port hasznalatat
# egy komponens moge rejti, hogy az index build ne kozvetlenul a facade-bol
# kezelje a chunking policy-t.

from __future__ import annotations

from typing import Any

from apps.knowledge.service.ports import ChunkBuilderPort


class ChunkingService:
    def __init__(self, *, chunk_builder: ChunkBuilderPort) -> None:
        self._chunk_builder = chunk_builder

    def build_chunks(self, text: str) -> list[Any]:
        return self._chunk_builder.build_chunks(text)


__all__ = ["ChunkingService"]
