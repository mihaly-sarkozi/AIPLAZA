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

    def list_indexed_for_training_item(
        self,
        training_item_id: str,
        *,
        knowledge_base_id: str | None = None,
    ) -> list[IndexedChunk]:
        with self._session_factory() as session:
            query = select(IndexedChunk).where(
                IndexedChunk.training_item_id == training_item_id,
                IndexedChunk.status == "INDEXED",
            )
            if knowledge_base_id:
                query = query.where(IndexedChunk.knowledge_base_id == knowledge_base_id)
            rows = list(session.execute(query).scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    def list_indexed_for_knowledge_base(self, knowledge_base_id: str) -> list[IndexedChunk]:
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(IndexedChunk).where(
                        IndexedChunk.knowledge_base_id == knowledge_base_id,
                        IndexedChunk.status == "INDEXED",
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows

    def list_for_indexing_job(self, indexing_job_id: str, *, statuses: list[str] | None = None) -> list[IndexedChunk]:
        with self._session_factory() as session:
            query = select(IndexedChunk).where(IndexedChunk.indexing_job_id == indexing_job_id)
            if statuses:
                query = query.where(IndexedChunk.status.in_(statuses))
            rows = list(session.execute(query).scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    def list_by_chunk_ids(
        self,
        chunk_ids: list[str],
        *,
        knowledge_base_id: str,
        statuses: list[str] | None = None,
    ) -> list[IndexedChunk]:
        if not chunk_ids:
            return []
        with self._session_factory() as session:
            query = select(IndexedChunk).where(
                IndexedChunk.knowledge_base_id == knowledge_base_id,
                IndexedChunk.chunk_id.in_(chunk_ids),
            )
            if statuses:
                query = query.where(IndexedChunk.status.in_(statuses))
            rows = list(session.execute(query).scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    def update_chunk_status(
        self,
        row_id: str,
        *,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        metadata_patch: dict | None = None,
    ) -> None:
        now = utc_now_naive()
        with self._session_factory() as session:
            row = session.get(IndexedChunk, row_id)
            if row is None:
                return
            row.status = status
            row.error_code = error_code
            row.error_message = (error_message or "")[:4000] or None
            meta = dict(row.metadata_json or {})
            if metadata_patch:
                meta.update(metadata_patch)
            row.metadata_json = meta
            row.updated_at = now
            session.commit()


__all__ = ["IndexedChunkRepository"]
