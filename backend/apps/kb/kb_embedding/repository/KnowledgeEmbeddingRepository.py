from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_embedding.orm.KnowledgeEmbedding import KnowledgeEmbedding
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class KnowledgeEmbeddingRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def find_existing(
        self,
        *,
        knowledge_base_id: str,
        training_item_id: str,
        chunk_id: str,
        embedding_model: str,
        embedding_input_hash: str,
    ) -> KnowledgeEmbedding | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(KnowledgeEmbedding)
                    .where(
                        KnowledgeEmbedding.knowledge_base_id == knowledge_base_id,
                        KnowledgeEmbedding.training_item_id == training_item_id,
                        KnowledgeEmbedding.chunk_id == chunk_id,
                        KnowledgeEmbedding.embedding_model == embedding_model,
                        KnowledgeEmbedding.embedding_input_hash == embedding_input_hash,
                        KnowledgeEmbedding.status == "COMPLETED",
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row

    def upsert_embedding(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        chunk_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_dimension: int,
        embedding_vector: list[float] | None,
        vector_hash: str | None,
        content_hash: str | None,
        embedding_input_hash: str | None,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> KnowledgeEmbedding:
        with self._session_factory() as session:
            existing = (
                session.execute(
                    select(KnowledgeEmbedding)
                    .where(
                        KnowledgeEmbedding.embedding_job_id == embedding_job_id,
                        KnowledgeEmbedding.chunk_id == chunk_id,
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if existing is None:
                row = KnowledgeEmbedding(
                    id=new_id("emb"),
                    tenant_slug=tenant_slug,
                    knowledge_base_id=knowledge_base_id,
                    training_item_id=training_item_id,
                    chunk_id=chunk_id,
                    discovery_job_id=discovery_job_id,
                    embedding_job_id=embedding_job_id,
                    embedding_provider=embedding_provider,
                    embedding_model=embedding_model,
                    embedding_dimension=embedding_dimension,
                    embedding_vector=embedding_vector,
                    vector_hash=vector_hash,
                    content_hash=content_hash,
                    embedding_input_hash=embedding_input_hash,
                    status=status,
                    error_code=error_code,
                    error_message=(error_message or "")[:4000] or None,
                    metadata_json=dict(metadata or {}),
                )
                session.add(row)
            else:
                row = existing
                row.embedding_vector = embedding_vector
                row.vector_hash = vector_hash
                row.content_hash = content_hash
                row.embedding_input_hash = embedding_input_hash
                row.status = status
                row.error_code = error_code
                row.error_message = (error_message or "")[:4000] or None
                row.metadata_json = dict(metadata or {})
                row.updated_at = utc_now_naive()
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_for_job(self, embedding_job_id: str, *, status: str | None = None) -> list[KnowledgeEmbedding]:
        with self._session_factory() as session:
            query = select(KnowledgeEmbedding).where(
                KnowledgeEmbedding.embedding_job_id == embedding_job_id
            )
            if status is not None:
                query = query.where(KnowledgeEmbedding.status == status)
            rows = list(session.execute(query).scalars().all())
            for row in rows:
                session.expunge(row)
            return rows

    def count_by_status(self, embedding_job_id: str) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(KnowledgeEmbedding.status, KnowledgeEmbedding.id)
                .where(KnowledgeEmbedding.embedding_job_id == embedding_job_id)
            ).all()
        counts: dict[str, int] = {}
        for status, _ in rows:
            counts[status] = counts.get(status, 0) + 1
        return counts


__all__ = ["KnowledgeEmbeddingRepository"]
