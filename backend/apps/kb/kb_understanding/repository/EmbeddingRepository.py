from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/EmbeddingRepository.py
# Feladat: Embedding perzisztencia, chunk-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.orm.KnowledgeEmbedding import KnowledgeEmbedding


class EmbeddingRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_chunks(self, chunk_ids: list[str], embeddings: list[KnowledgeEmbedding]) -> int:
        with self._session_factory() as session:
            if chunk_ids:
                session.execute(
                    delete(KnowledgeEmbedding).where(KnowledgeEmbedding.chunk_id.in_(chunk_ids))
                )
            for embedding in embeddings:
                session.add(embedding)
            session.commit()
            return len(embeddings)

    def count_for_chunks(self, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0
        with self._session_factory() as session:
            return int(
                session.execute(
                    select(func.count(KnowledgeEmbedding.id)).where(
                        KnowledgeEmbedding.chunk_id.in_(chunk_ids)
                    )
                ).scalar()
                or 0
            )


__all__ = ["EmbeddingRepository"]
