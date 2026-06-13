from __future__ import annotations

# backend/apps/kb/kb_understanding/repository/UnderstandingJobRepository.py
# Feladat: Megértési job perzisztencia — létrehozás, státuszváltás, lezárás, retry.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import select

from apps.kb.kb_understanding.enums.UnderstandingStatus import TERMINAL_STATUSES, UnderstandingStatus
from apps.kb.kb_understanding.orm.UnderstandingJob import UnderstandingJob
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class UnderstandingJobRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create_job(
        self,
        *,
        training_item_id: str,
        training_batch_id: str,
        knowledge_base_id: str,
        created_by: int | None,
        metadata: dict | None = None,
    ) -> UnderstandingJob:
        job = UnderstandingJob(
            id=new_id("und_job"),
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            knowledge_base_id=knowledge_base_id,
            status=UnderstandingStatus.CREATED.value,
            created_by=created_by,
            metadata_json=dict(metadata or {}),
        )
        with self._session_factory() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)
        return job

    def get_job(self, job_id: str) -> UnderstandingJob | None:
        with self._session_factory() as session:
            job = session.get(UnderstandingJob, job_id)
            if job is not None:
                session.expunge(job)
            return job

    def get_latest_job_for_item(self, training_item_id: str) -> UnderstandingJob | None:
        with self._session_factory() as session:
            job = (
                session.execute(
                    select(UnderstandingJob)
                    .where(UnderstandingJob.training_item_id == training_item_id)
                    .order_by(UnderstandingJob.created_at.desc(), UnderstandingJob.id.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if job is not None:
                session.expunge(job)
            return job

    def has_active_job_for_item(self, training_item_id: str) -> bool:
        """Aktív = nem lezárt státuszú job az itemhez."""
        terminal_values = [status.value for status in TERMINAL_STATUSES]
        with self._session_factory() as session:
            job = (
                session.execute(
                    select(UnderstandingJob.id)
                    .where(
                        UnderstandingJob.training_item_id == training_item_id,
                        UnderstandingJob.status.notin_(terminal_values),
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return job is not None

    def set_status(self, job_id: str, status: UnderstandingStatus) -> None:
        with self._session_factory() as session:
            job = session.get(UnderstandingJob, job_id)
            if job is None:
                return
            if job.started_at is None and status not in (UnderstandingStatus.CREATED, UnderstandingStatus.QUEUED):
                job.started_at = utc_now_naive()
            job.status = status.value
            session.commit()

    def mark_completed(self, job_id: str, status: UnderstandingStatus) -> None:
        with self._session_factory() as session:
            job = session.get(UnderstandingJob, job_id)
            if job is None:
                return
            job.status = status.value
            job.completed_at = utc_now_naive()
            session.commit()

    def mark_failed(
        self,
        job_id: str,
        *,
        status: UnderstandingStatus,
        error_code: str,
        error_message: str | None = None,
        retryable: bool = False,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(UnderstandingJob, job_id)
            if job is None:
                return
            job.status = status.value
            job.error_code = error_code
            job.error_message = (error_message or "")[:4000] or None
            job.retryable = retryable
            job.completed_at = utc_now_naive()
            session.commit()

    def increment_retry(self, job_id: str) -> None:
        with self._session_factory() as session:
            job = session.get(UnderstandingJob, job_id)
            if job is None:
                return
            job.retry_count = int(job.retry_count or 0) + 1
            job.status = UnderstandingStatus.QUEUED.value
            job.error_code = None
            job.error_message = None
            job.completed_at = None
            session.commit()

    def update_extract_progress(self, job_id: str, progress: dict) -> None:
        with self._session_factory() as session:
            job = session.get(UnderstandingJob, job_id)
            if job is None:
                return
            metadata = dict(job.metadata_json or {})
            metadata["extract_progress"] = dict(progress)
            job.metadata_json = metadata
            session.commit()


__all__ = ["UnderstandingJobRepository"]
