from __future__ import annotations

# backend/apps/kb/kb_understanding/ports/EntityExtractorInterface.py
# Feladat: Entitáskinyerő szerződés — LLM vagy más implementáció cserélhető adapterként.
# Sárközi Mihály - 2026.06.11

from typing import Protocol

from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto


class EntityExtractorInterface(Protocol):
    def extract_entities(self, chunks: list[tuple[str, str]]) -> list[KnowledgeEntityDto]:
        """``chunks``: (chunk_id, text) párok; kimenet: chunk_ids-szel ellátott entitások."""
        ...


__all__ = ["EntityExtractorInterface"]
