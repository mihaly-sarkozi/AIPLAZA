from __future__ import annotations

from apps.kb.kb_ingest.dto.IngestRunListResponse import (
    IngestRunListResponse,
    IngestRunListSummaryResponse,
)
from apps.kb.kb_ingest.mapper.ingest_run_mapper import to_ingest_run_response
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository


class ListIngestRunsService:
    def __init__(self, repository: TrainingRepository) -> None:
        self._repository = repository

    def list_runs(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> IngestRunListResponse:
        batches, total = self._repository.list_batches_for_knowledge_base(
            knowledge_base_id,
            limit=limit,
            offset=offset,
        )
        batch_ids = [batch.id for batch in batches]
        items_by_batch = self._repository.list_items_for_batches(batch_ids)
        runs = [
            to_ingest_run_response(batch, items_by_batch.get(batch.id, []))
            for batch in batches
        ]
        total_item_count = sum(len(run.items) for run in runs)
        total_char_count = sum(
            int(item.metadata.get("char_count") or 0)
            for run in runs
            for item in run.items
        )
        return IngestRunListResponse(
            items=runs,
            total_count=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(runs)) < total,
            summary=IngestRunListSummaryResponse(
                total_run_count=total,
                total_item_count=total_item_count,
                total_char_count=total_char_count,
                total_sentence_count=0,
            ),
        )


__all__ = ["ListIngestRunsService"]
