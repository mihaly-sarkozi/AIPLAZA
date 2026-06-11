from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/ChunkRepository.py
# Feladat: Tudás-chunk perzisztencia, dokumentum-szintű replace szemantikával.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk


class ChunkRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_document(self, document_id: str, chunks: list[KnowledgeChunk]) -> int:
        with self._session_factory() as session:
            session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
            )
            for chunk in chunks:
                session.add(chunk)
            session.commit()
            return len(chunks)

    def list_for_document(self, document_id: str) -> list[KnowledgeChunk]:
        with self._session_factory() as session:
            chunks = list(
                session.execute(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == document_id)
                    .order_by(KnowledgeChunk.order_index.asc())
                )
                .scalars()
                .all()
            )
            for chunk in chunks:
                session.expunge(chunk)
            return chunks

    def count_for_document(self, document_id: str) -> int:
        with self._session_factory() as session:
            return int(
                session.execute(
                    select(func.count(KnowledgeChunk.id)).where(
                        KnowledgeChunk.document_id == document_id
                    )
                ).scalar()
                or 0
            )

    def max_version_for_document(self, document_id: str) -> int:
        with self._session_factory() as session:
            return int(
                session.execute(
                    select(func.max(KnowledgeChunk.version)).where(
                        KnowledgeChunk.document_id == document_id
                    )
                ).scalar()
                or 0
            )


__all__ = ["ChunkRepository"]
