from __future__ import annotations

from typing import Protocol

from apps.kb.kb_understanding.dto.UnderstandingStatusResponse import UnderstandingStatusResponse
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.mapper.understanding_mapper import job_to_response, processing_event_to_step_response
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)
from apps.kb.shared.ports.processing_event_reader import ProcessingEventReaderPort

_UNDERSTANDING_MODULE = "kb_understanding"


class _StepOutputEnricher(Protocol):
    def enrich(
        self,
        *,
        module: str,
        step: str,
        training_item_id: str | None,
        output_summary_json: dict | None,
    ) -> dict: ...


class UnderstandingStatusService:
    def __init__(
        self,
        job_repository: UnderstandingJobRepository,
        event_reader: ProcessingEventReaderPort,
        chunk_repository: ChunkRepository,
        *,
        output_enricher: _StepOutputEnricher | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._event_reader = event_reader
        self._chunk_repository = chunk_repository
        self._output_enricher = output_enricher

    def get_status(self, *, knowledge_base_id: str, training_item_id: str) -> UnderstandingStatusResponse:
        job = self._job_repository.get_latest_job_for_item(training_item_id)
        if job is None or job.knowledge_base_id != knowledge_base_id:
            raise UnderstandingNotFoundError(
                UnderstandingErrorCode.JOB_NOT_FOUND, item_id=training_item_id
            )
        steps = self._event_reader.list_for_job(job.id, module=_UNDERSTANDING_MODULE)
        step_responses = [processing_event_to_step_response(event) for event in steps]
        if self._output_enricher is not None:
            step_responses = [
                step.model_copy(
                    update={
                        "output_summary": self._output_enricher.enrich(
                            module=_UNDERSTANDING_MODULE,
                            step=step.step,
                            training_item_id=training_item_id,
                            output_summary_json=step.output_summary,
                        )
                    }
                )
                for step in step_responses
            ]
        chunks = self._chunk_repository.list_for_document(training_item_id)
        return UnderstandingStatusResponse(
            job=job_to_response(job),
            steps=step_responses,
            chunk_count=len(chunks),
        )


__all__ = ["UnderstandingStatusService"]
