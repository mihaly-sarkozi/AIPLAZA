from __future__ import annotations

from apps.kb.kb_ingest.dto.IngestRunListResponse import (
    IngestRunListResponse,
    IngestRunListSummaryResponse,
)
from apps.kb.kb_ingest.mapper.ingest_run_mapper import (
    to_ingest_run_response,
    to_synthetic_ingest_run_from_items,
)
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
        if total == 0:
            items, item_total = self._repository.list_items_for_knowledge_base(
                knowledge_base_id,
                limit=limit,
                offset=offset,
            )
            if item_total > 0:
                grouped: dict[str, list] = {}
                for item in items:
                    grouped.setdefault(item.training_batch_id, []).append(item)
                runs = [
                    to_synthetic_ingest_run_from_items(knowledge_base_id, batch_id, batch_items)
                    for batch_id, batch_items in sorted(
                        grouped.items(),
                        key=lambda pair: min(row.created_at for row in pair[1]),
                        reverse=True,
                    )
                ]
                total_item_count = sum(len(run.items) for run in runs)
                total_char_count = sum(
                    int(item.metadata.get("char_count") or 0)
                    for run in runs
                    for item in run.items
                )
                return IngestRunListResponse(
                    items=runs,
                    total_count=item_total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(items)) < item_total,
                    summary=IngestRunListSummaryResponse(
                        total_run_count=len(runs),
                        total_item_count=total_item_count,
                        total_char_count=total_char_count,
                        total_sentence_count=0,
                    ),
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
