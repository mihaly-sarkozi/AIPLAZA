from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/understanding_mapper.py
# Feladat: Job / lépésfutás ORM → HTTP válasz átalakítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.UnderstandingJobResponse import UnderstandingJobResponse
from apps.kb.kb_understanding.dto.UnderstandingStepRunResponse import UnderstandingStepRunResponse
from apps.kb.kb_understanding.orm.UnderstandingJob import UnderstandingJob
from apps.kb.shared.ports.processing_event_reader import ProcessingStepEventView


def job_to_response(job: UnderstandingJob) -> UnderstandingJobResponse:
    return UnderstandingJobResponse(
        id=job.id,
        training_item_id=job.training_item_id,
        training_batch_id=job.training_batch_id,
        knowledge_base_id=job.knowledge_base_id,
        status=job.status,
        error_code=job.error_code,
        error_message=job.error_message,
        retryable=bool(job.retryable),
        retry_count=int(job.retry_count or 0),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def processing_event_to_step_response(event: ProcessingStepEventView) -> UnderstandingStepRunResponse:
    return UnderstandingStepRunResponse(
        step=event.step,
        status=event.status,
        duration_ms=int(event.duration_ms or 0),
        input_summary=dict(event.input_summary),
        output_summary=dict(event.output_summary),
        error_code=event.error_code,
        error_message=event.error_message,
        created_at=event.created_at,
    )


__all__ = ["job_to_response", "processing_event_to_step_response"]
