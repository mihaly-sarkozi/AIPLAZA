from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/EnrichmentRepository.py
# Feladat: Enrichment perzisztencia, job-szintű replace szemantikával (chunk_id-hoz kötve).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, select

from apps.kb.kb_understanding.orm.KnowledgeEnrichment import KnowledgeEnrichment


class EnrichmentRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_chunks(self, chunk_ids: list[str], enrichments: list[KnowledgeEnrichment]) -> int:
        with self._session_factory() as session:
            if chunk_ids:
                session.execute(
                    delete(KnowledgeEnrichment).where(KnowledgeEnrichment.chunk_id.in_(chunk_ids))
                )
            for enrichment in enrichments:
                session.add(enrichment)
            session.commit()
            return len(enrichments)

    def list_for_chunks(self, chunk_ids: list[str]) -> list[KnowledgeEnrichment]:
        if not chunk_ids:
            return []
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(KnowledgeEnrichment).where(KnowledgeEnrichment.chunk_id.in_(chunk_ids))
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows


__all__ = ["EnrichmentRepository"]
