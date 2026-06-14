from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_embedding.enums.EmbeddingStatus import TERMINAL_STATUSES, EmbeddingStatus
from apps.kb.kb_embedding.orm.EmbeddingJob import EmbeddingJob
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class EmbeddingJobRepository:
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
        created_by: int | None,
        embedding_model: str,
        embedding_provider: str,
        embedding_dimension: int,
        chunks_total: int,
        metadata: dict | None = None,
    ) -> EmbeddingJob:
        job = EmbeddingJob(
            id=new_id("emb_job"),
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id,
            discovery_job_id=discovery_job_id,
            status=EmbeddingStatus.PENDING.value,
            chunks_total=chunks_total,
            embedding_model=embedding_model,
            embedding_provider=embedding_provider,
            embedding_dimension=embedding_dimension,
            created_by=created_by,
            metadata_json=dict(metadata or {}),
        )
        with self._session_factory() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)
        return job

    def get_job(self, job_id: str) -> EmbeddingJob | None:
        with self._session_factory() as session:
            job = session.get(EmbeddingJob, job_id)
            if job is not None:
                session.expunge(job)
            return job

    def has_active_job_for_discovery(self, discovery_job_id: str) -> bool:
        terminal_values = [status.value for status in TERMINAL_STATUSES]
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(EmbeddingJob.id)
                    .where(
                        EmbeddingJob.discovery_job_id == discovery_job_id,
                        EmbeddingJob.status.notin_(terminal_values),
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return row is not None

    def set_status(self, job_id: str, status: EmbeddingStatus) -> None:
        with self._session_factory() as session:
            job = session.get(EmbeddingJob, job_id)
            if job is None:
                return
            if job.started_at is None and status == EmbeddingStatus.RUNNING:
                job.started_at = utc_now_naive()
            job.status = status.value
            session.commit()

    def update_progress(
        self,
        job_id: str,
        *,
        chunks_embedded: int,
        chunks_failed: int,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(EmbeddingJob, job_id)
            if job is None:
                return
            job.chunks_embedded = chunks_embedded
            job.chunks_failed = chunks_failed
            session.commit()

    def mark_finished(
        self,
        job_id: str,
        status: EmbeddingStatus,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(EmbeddingJob, job_id)
            if job is None:
                return
            job.status = status.value
            job.error_code = error_code
            job.error_message = (error_message or "")[:4000] or None
            job.finished_at = utc_now_naive()
            session.commit()


__all__ = ["EmbeddingJobRepository"]
