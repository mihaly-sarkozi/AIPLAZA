from __future__ import annotations

# backend/apps/kb/kb_understanding/service/UnderstandingStatusService.py
# Feladat: Egy ingest item megértési állapotának lekérdezése — job + lépésfutások + számlálók.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.UnderstandingStatusResponse import UnderstandingStatusResponse
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.mapper.understanding_mapper import job_to_response, step_run_to_response
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.EmbeddingRepository import EmbeddingRepository
from apps.kb.kb_understanding.repository.EntityRepository import EntityRepository
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)
from apps.kb.kb_understanding.repository.UnderstandingStepRunRepository import (
    UnderstandingStepRunRepository,
)


class UnderstandingStatusService:
    def __init__(
        self,
        job_repository: UnderstandingJobRepository,
        step_run_repository: UnderstandingStepRunRepository,
        chunk_repository: ChunkRepository,
        entity_repository: EntityRepository,
        embedding_repository: EmbeddingRepository,
    ) -> None:
        self._job_repository = job_repository
        self._step_run_repository = step_run_repository
        self._chunk_repository = chunk_repository
        self._entity_repository = entity_repository
        self._embedding_repository = embedding_repository

    def get_status(self, *, knowledge_base_id: str, training_item_id: str) -> UnderstandingStatusResponse:
        job = self._job_repository.get_latest_job_for_item(training_item_id)
        if job is None or job.knowledge_base_id != knowledge_base_id:
            raise UnderstandingNotFoundError(
                UnderstandingErrorCode.JOB_NOT_FOUND, item_id=training_item_id
            )
        steps = self._step_run_repository.list_for_job(job.id)
        chunks = self._chunk_repository.list_for_document(training_item_id)
        return UnderstandingStatusResponse(
            job=job_to_response(job),
            steps=[step_run_to_response(run) for run in steps],
            chunk_count=len(chunks),
            entity_count=self._entity_repository.count_for_document(training_item_id),
            embedding_count=self._embedding_repository.count_for_chunks(
                [chunk.id for chunk in chunks]
            ),
        )


__all__ = ["UnderstandingStatusService"]
