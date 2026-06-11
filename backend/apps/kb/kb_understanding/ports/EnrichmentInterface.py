from __future__ import annotations

# backend/apps/kb/kb_understanding/ports/EnrichmentInterface.py
# Feladat: Tudás-enrichment szerződés — LLM implementáció cserélhető adapterként.
# Sárközi Mihály - 2026.06.11

from typing import Protocol

from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto


class EnrichmentInterface(Protocol):
    def enrich_chunk(self, chunk_id: str, text: str) -> KnowledgeEnrichmentDto: ...


__all__ = ["EnrichmentInterface"]
