from __future__ import annotations

from sqlalchemy import desc, select

from apps.kb.kb_indexing.enums.IndexingStatus import TERMINAL_STATUSES, IndexingStatus
from apps.kb.kb_indexing.orm.IndexedChunk import IndexedChunk
from apps.kb.kb_indexing.orm.IndexingJob import IndexingJob
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class IndexingJobRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create_job(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        understanding_job_id: str,
        discovery_job_id: str,
        embedding_job_id: str,
        created_by: int | None,
        collection_name: str,
        vector_size: int,
        distance_metric: str,
        chunks_total: int,
        metadata: dict | None = None,
    ) -> IndexingJob:
        job = IndexingJob(
            id=new_id("idx_job"),
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            embedding_job_id=embedding_job_id,
            status=IndexingStatus.PENDING.value,
            collection_name=collection_name,
            vector_size=vector_size,
            distance_metric=distance_metric,
            chunks_total=chunks_total,
            created_by=created_by,
            metadata_json=dict(metadata or {}),
        )
        with self._session_factory() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)
        return job

    def get_job(self, job_id: str) -> IndexingJob | None:
        with self._session_factory() as session:
            job = session.get(IndexingJob, job_id)
            if job is not None:
                session.expunge(job)
            return job

    def has_active_job_for_embedding(self, embedding_job_id: str) -> bool:
        return self.get_active_job_id_for_embedding(embedding_job_id) is not None

    def get_active_job_id_for_embedding(self, embedding_job_id: str) -> str | None:
        terminal_values = [status.value for status in TERMINAL_STATUSES]
        with self._session_factory() as session:
            return (
                session.execute(
                    select(IndexingJob.id)
                    .where(
                        IndexingJob.embedding_job_id == embedding_job_id,
                        IndexingJob.status.notin_(terminal_values),
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )

    def get_active_job_id_for_training_item(self, training_item_id: str) -> str | None:
        terminal_values = [status.value for status in TERMINAL_STATUSES]
        with self._session_factory() as session:
            return (
                session.execute(
                    select(IndexingJob.id)
                    .where(
                        IndexingJob.training_item_id == training_item_id,
                        IndexingJob.status.notin_(terminal_values),
                    )
                    .order_by(IndexingJob.created_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )

    def get_latest_for_training_item(self, training_item_id: str) -> IndexingJob | None:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(IndexingJob)
                    .where(IndexingJob.training_item_id == training_item_id)
                    .order_by(IndexingJob.created_at.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row

    def set_status(self, job_id: str, status: IndexingStatus) -> None:
        with self._session_factory() as session:
            job = session.get(IndexingJob, job_id)
            if job is None:
                return
            if job.started_at is None and status == IndexingStatus.RUNNING:
                job.started_at = utc_now_naive()
            job.status = status.value
            session.commit()

    def update_progress(
        self,
        job_id: str,
        *,
        chunks_indexed: int,
        chunks_failed: int,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(IndexingJob, job_id)
            if job is None:
                return
            job.chunks_indexed = chunks_indexed
            job.chunks_failed = chunks_failed
            session.commit()

    def mark_finished(
        self,
        job_id: str,
        status: IndexingStatus,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(IndexingJob, job_id)
            if job is None:
                return
            job.status = status.value
            job.error_code = error_code
            job.error_message = (error_message or "")[:4000] or None
            job.finished_at = utc_now_naive()
            session.commit()


__all__ = ["IndexingJobRepository"]
