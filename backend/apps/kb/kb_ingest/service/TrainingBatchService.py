from __future__ import annotations

from apps.kb.kb_ingest.dto.TrainingBatchStatusResponse import TrainingBatchStatusResponse
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.mapper.training_response_mapper import (
    to_batch_summary_response,
    to_item_summary_response,
)
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository


class TrainingBatchService:
    def __init__(self, *, repository: TrainingRepository) -> None:
        self._repository = repository

    def get_status(self, batch_id: str, *, tenant: str | None = None) -> TrainingBatchStatusResponse:
        batch = self._repository.get_batch(batch_id, tenant=tenant)
        if batch is None:
            raise TrainingNotFoundError(TrainingErrorCode.BATCH_NOT_FOUND)
        items = self._repository.list_items_for_batch(batch_id)
        return TrainingBatchStatusResponse(
            batch=to_batch_summary_response(batch, items=items),
            items=[to_item_summary_response(item) for item in items],
        )


__all__ = ["TrainingBatchService"]
