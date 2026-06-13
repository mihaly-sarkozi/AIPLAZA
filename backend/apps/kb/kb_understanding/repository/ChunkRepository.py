from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, func, select

from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk
from apps.kb.shared.contracts import ChunkLanguageUpdate


class ChunkRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def replace_for_document(
        self,
        document_id: str,
        chunks: Iterable[KnowledgeChunk],
        *,
        batch_size: int = 100,
    ) -> int:
        with self._session_factory() as session:
            try:
                session.execute(
                    delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
                )
                total = 0
                batch: list[KnowledgeChunk] = []
                for chunk in chunks:
                    batch.append(chunk)
                    if len(batch) >= batch_size:
                        session.add_all(batch)
                        session.flush()
                        total += len(batch)
                        batch.clear()
                if batch:
                    session.add_all(batch)
                    session.flush()
                    total += len(batch)
                session.commit()
                return total
            except Exception:
                session.rollback()
                raise

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

    def bulk_update_chunk_language(self, results: Iterable[ChunkLanguageUpdate]) -> int:
        updates = list(results)
        if not updates:
            return 0
        with self._session_factory() as session:
            updated = 0
            for item in updates:
                chunk = session.get(KnowledgeChunk, item.chunk_id)
                if chunk is None:
                    continue
                chunk.language_code = item.language_code
                chunk.language_confidence = item.language_confidence
                chunk.language_detected_by = item.language_detected_by
                metadata = dict(chunk.metadata_json or {})
                metadata["language"] = dict(item.language_metadata or {})
                chunk.metadata_json = metadata
                updated += 1
            session.commit()
            return updated


__all__ = ["ChunkRepository"]
