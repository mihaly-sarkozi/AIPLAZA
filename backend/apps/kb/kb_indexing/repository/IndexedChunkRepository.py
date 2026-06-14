from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_indexing.orm.IndexedChunk import IndexedChunk
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class IndexedChunkRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def upsert_indexed_chunk(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        chunk_id: str,
        embedding_id: str,
        indexing_job_id: str,
        qdrant_collection: str,
        qdrant_point_id: str,
        payload_hash: str | None,
        vector_hash: str | None,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> IndexedChunk:
        with self._session_factory() as session:
            existing = (
                session.execute(
                    select(IndexedChunk)
                    .where(
                        IndexedChunk.indexing_job_id == indexing_job_id,
                        IndexedChunk.chunk_id == chunk_id,
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            now = utc_now_naive()
            if existing is None:
                row = IndexedChunk(
                    id=new_id("idx_chunk"),
                    tenant_slug=tenant_slug,
                    knowledge_base_id=knowledge_base_id,
                    training_item_id=training_item_id,
                    chunk_id=chunk_id,
                    embedding_id=embedding_id,
                    indexing_job_id=indexing_job_id,
                    qdrant_collection=qdrant_collection,
                    qdrant_point_id=qdrant_point_id,
                    payload_hash=payload_hash,
                    vector_hash=vector_hash,
                    indexed_at=now if status == "INDEXED" else None,
                    status=status,
                    error_code=error_code,
                    error_message=(error_message or "")[:4000] or None,
                    metadata_json=dict(metadata or {}),
                )
                session.add(row)
            else:
                row = existing
                row.embedding_id = embedding_id
                row.qdrant_collection = qdrant_collection
                row.qdrant_point_id = qdrant_point_id
                row.payload_hash = payload_hash
                row.vector_hash = vector_hash
                row.indexed_at = now if status == "INDEXED" else row.indexed_at
                row.status = status
                row.error_code = error_code
                row.error_message = (error_message or "")[:4000] or None
                row.metadata_json = dict(metadata or {})
                row.updated_at = now
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_for_job(self, indexing_job_id: str) -> list[IndexedChunk]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(IndexedChunk).where(IndexedChunk.indexing_job_id == indexing_job_id)
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows

    def count_by_status(self, indexing_job_id: str) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(IndexedChunk.status, IndexedChunk.id)
                .where(IndexedChunk.indexing_job_id == indexing_job_id)
            ).all()
        counts: dict[str, int] = {}
        for status, _ in rows:
            counts[status] = counts.get(status, 0) + 1
        return counts


__all__ = ["IndexedChunkRepository"]
