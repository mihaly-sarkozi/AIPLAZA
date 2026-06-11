from __future__ import annotations

# backend/apps/kb/kb_understanding/service/RetryUnderstandingService.py
# Feladat: RETRYABLE / FAILED megértési job újra-sorbaállítása.
# Sárközi Mihály - 2026.06.11

from typing import Callable

from apps.kb.kb_understanding.dto.UnderstandingJobResponse import UnderstandingJobResponse
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.enums.UnderstandingStatus import TERMINAL_STATUSES, UnderstandingStatus
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.events.understanding_requested_event import (
    add_understanding_retry_event,
)
from apps.kb.kb_understanding.mapper.understanding_mapper import job_to_response
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)

_RETRYABLE_STATUSES = {UnderstandingStatus.RETRYABLE.value, UnderstandingStatus.FAILED.value}


class RetryUnderstandingService:
    def __init__(
        self,
        job_repository: UnderstandingJobRepository,
        emit_retry: Callable[..., None] = add_understanding_retry_event,
    ) -> None:
        self._job_repository = job_repository
        self._emit_retry = emit_retry

    def retry(
        self,
        *,
        knowledge_base_id: str,
        training_item_id: str,
        tenant_slug: str | None,
        force: bool = False,
    ) -> UnderstandingJobResponse:
        job = self._job_repository.get_latest_job_for_item(training_item_id)
        if job is None or job.knowledge_base_id != knowledge_base_id:
            raise UnderstandingNotFoundError(
                UnderstandingErrorCode.JOB_NOT_FOUND, item_id=training_item_id
            )
        terminal_values = {status.value for status in TERMINAL_STATUSES}
        if job.status not in _RETRYABLE_STATUSES:
            if not (force and job.status in terminal_values):
                raise UnderstandingProcessingError(
                    UnderstandingErrorCode.JOB_NOT_RETRYABLE, status=job.status
                )

        self._job_repository.increment_retry(job.id)
        refreshed = self._job_repository.get_job(job.id)
        self._emit_retry(
            tenant_slug=tenant_slug,
            training_batch_id=job.training_batch_id,
            training_item_id=training_item_id,
            knowledge_base_id=knowledge_base_id,
            created_by=job.created_by,
            retry_count=int(refreshed.retry_count or 0) if refreshed else 0,
        )
        return job_to_response(refreshed or job)


__all__ = ["RetryUnderstandingService"]
