from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/understanding_mapper.py
# Feladat: Job / lépésfutás ORM → HTTP válasz átalakítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.UnderstandingJobResponse import UnderstandingJobResponse
from apps.kb.kb_understanding.dto.UnderstandingStepRunResponse import UnderstandingStepRunResponse
from apps.kb.kb_understanding.orm.UnderstandingJob import UnderstandingJob
from apps.kb.kb_understanding.orm.UnderstandingStepRun import UnderstandingStepRun


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


def step_run_to_response(run: UnderstandingStepRun) -> UnderstandingStepRunResponse:
    return UnderstandingStepRunResponse(
        step=run.step,
        status=run.status,
        duration_ms=int(run.duration_ms or 0),
        input_summary=dict(run.input_summary or {}),
        output_summary=dict(run.output_summary or {}),
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
    )


__all__ = ["job_to_response", "step_run_to_response"]
