from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_discovery.enums.DiscoveryStatus import TERMINAL_STATUSES, DiscoveryStatus
from apps.kb.kb_discovery.orm.DiscoveryJob import DiscoveryJob
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


class DiscoveryJobRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create_job(
        self,
        *,
        understanding_job_id: str,
        training_item_id: str,
        training_batch_id: str,
        knowledge_base_id: str,
        created_by: int | None,
        metadata: dict | None = None,
    ) -> DiscoveryJob:
        job = DiscoveryJob(
            id=new_id("disc_job"),
            understanding_job_id=understanding_job_id,
            training_item_id=training_item_id,
            training_batch_id=training_batch_id,
            knowledge_base_id=knowledge_base_id,
            status=DiscoveryStatus.CREATED.value,
            created_by=created_by,
            metadata_json=dict(metadata or {}),
        )
        with self._session_factory() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)
        return job

    def get_job(self, job_id: str) -> DiscoveryJob | None:
        with self._session_factory() as session:
            job = session.get(DiscoveryJob, job_id)
            if job is not None:
                session.expunge(job)
            return job

    def get_latest_job_for_item(self, training_item_id: str) -> DiscoveryJob | None:
        with self._session_factory() as session:
            job = (
                session.execute(
                    select(DiscoveryJob)
                    .where(DiscoveryJob.training_item_id == training_item_id)
                    .order_by(DiscoveryJob.created_at.desc(), DiscoveryJob.id.desc())
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if job is not None:
                session.expunge(job)
            return job

    def has_active_job_for_item(self, training_item_id: str) -> bool:
        terminal_values = [status.value for status in TERMINAL_STATUSES]
        with self._session_factory() as session:
            job = (
                session.execute(
                    select(DiscoveryJob.id)
                    .where(
                        DiscoveryJob.training_item_id == training_item_id,
                        DiscoveryJob.status.notin_(terminal_values),
                    )
                    .limit(1)
                )
                .scalars()
                .first()
            )
            return job is not None

    def set_status(self, job_id: str, status: DiscoveryStatus) -> None:
        with self._session_factory() as session:
            job = session.get(DiscoveryJob, job_id)
            if job is None:
                return
            if job.started_at is None and status not in (DiscoveryStatus.CREATED, DiscoveryStatus.QUEUED):
                job.started_at = utc_now_naive()
            job.status = status.value
            session.commit()

    def mark_completed(self, job_id: str, status: DiscoveryStatus) -> None:
        with self._session_factory() as session:
            job = session.get(DiscoveryJob, job_id)
            if job is None:
                return
            job.status = status.value
            job.completed_at = utc_now_naive()
            session.commit()

    def mark_failed(
        self,
        job_id: str,
        *,
        status: DiscoveryStatus,
        error_code: str,
        error_message: str | None = None,
        retryable: bool = False,
    ) -> None:
        with self._session_factory() as session:
            job = session.get(DiscoveryJob, job_id)
            if job is None:
                return
            job.status = status.value
            job.error_code = error_code
            job.error_message = (error_message or "")[:4000] or None
            job.retryable = retryable
            job.completed_at = utc_now_naive()
            session.commit()

    def update_metadata(self, job_id: str, patch: dict) -> None:
        with self._session_factory() as session:
            job = session.get(DiscoveryJob, job_id)
            if job is None:
                return
            metadata = dict(job.metadata_json or {})
            metadata.update(patch)
            job.metadata_json = metadata
            session.commit()


__all__ = ["DiscoveryJobRepository"]
