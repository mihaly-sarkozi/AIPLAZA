from __future__ import annotations

from apps.kb.kb_ingest.dto.IngestRunListResponse import IngestItemResponse, IngestRunResponse
from apps.kb.kb_ingest.dto.TrainingBatchStatusResponse import TrainingBatchStatusResponse
from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_ingest.enums.TrainingItemStatus import TrainingItemStatus
from apps.kb.kb_ingest.mapper.training_response_mapper import (
    to_batch_summary_response,
    to_item_summary_response,
)
from apps.kb.kb_ingest.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_ingest.orm.TrainingItem import TrainingItem


def _completed_count(batch: TrainingBatch, items: list[TrainingItem]) -> int:
    status = str(batch.status or "")
    accepted = sum(1 for item in items if item.status == TrainingItemStatus.ACCEPTED.value)
    if status in (TrainingBatchStatus.COMPLETED.value, TrainingBatchStatus.PARTIAL_SUCCESS.value):
        return max(accepted, 1)
    return accepted


def _char_count(item: TrainingItem) -> int | None:
    metadata = dict(item.metadata_json or {})
    raw = metadata.get("char_count")
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def to_ingest_item_response(item: TrainingItem, *, index: int, batch_id: str, kb_id: str) -> IngestItemResponse:
    summary = to_item_summary_response(item)
    char_count = summary.char_count
    created_at = item.created_at
    updated_at = item.updated_at or created_at
    return IngestItemResponse(
        id=item.id,
        ingest_run_id=batch_id,
        corpus_uuid=kb_id,
        queue_order=index,
        input_type=summary.input_type,
        display_name=summary.title or summary.input_type,
        title=summary.title,
        status=str(summary.status),
        error_code=str(summary.error_code) if summary.error_code else None,
        error_message=summary.error_message,
        duplicate_of_item_id=item.duplicate_of_item_id,
        created_at=created_at,
        updated_at=updated_at,
        metadata={"char_count": char_count} if char_count is not None else {},
    )


def to_ingest_run_response(batch: TrainingBatch, items: list[TrainingItem]) -> IngestRunResponse:
    summary = to_batch_summary_response(batch, items=items)
    ingest_items = [
        to_ingest_item_response(item, index=index, batch_id=batch.id, kb_id=batch.knowledge_base_id)
        for index, item in enumerate(items)
    ]
    total_char_count = sum(_char_count(item) or 0 for item in items)
    metadata = dict(batch.metadata_json or {})
    if summary.progress:
        metadata["progress_summary"] = summary.progress
    if total_char_count > 0:
        metadata["total_char_count"] = total_char_count
    completed_at = batch.completed_at
    updated_at = batch.updated_at or batch.created_at
    return IngestRunResponse(
        id=batch.id,
        corpus_uuid=batch.knowledge_base_id,
        input_channel=batch.input_channel,
        status=str(summary.status),
        batch_size=int(summary.batch_size or 0),
        queued_count=int(batch.queued_count or 0),
        processing_count=0,
        completed_count=_completed_count(batch, items),
        failed_count=int(summary.failed_count or 0),
        duplicate_count=int(summary.duplicate_count or 0),
        rejected_count=int(summary.rejected_count or 0),
        created_at=batch.created_at,
        completed_at=completed_at,
        updated_at=updated_at or batch.created_at,
        created_by=int(batch.created_by),
        metadata=metadata,
        items=ingest_items,
        events=[],
    )


def to_synthetic_ingest_run_from_items(
    knowledge_base_id: str,
    batch_id: str,
    items: list[TrainingItem],
) -> IngestRunResponse:
    ingest_items = [
        to_ingest_item_response(item, index=index, batch_id=batch_id, kb_id=knowledge_base_id)
        for index, item in enumerate(items)
    ]
    total_char_count = sum(_char_count(item) or 0 for item in items)
    created_at = min(item.created_at for item in items)
    updated_at = max((item.updated_at or item.created_at) for item in items)
    accepted = sum(1 for item in items if item.status == TrainingItemStatus.ACCEPTED.value)
    failed = sum(1 for item in items if item.status == TrainingItemStatus.FAILED.value)
    duplicate = sum(1 for item in items if item.duplicate_of_item_id)
    rejected = sum(1 for item in items if item.status == TrainingItemStatus.REJECTED.value)
    metadata: dict = {"synthetic_run": True}
    if total_char_count > 0:
        metadata["total_char_count"] = total_char_count
    return IngestRunResponse(
        id=batch_id,
        corpus_uuid=knowledge_base_id,
        input_channel="legacy",
        status=TrainingBatchStatus.COMPLETED.value,
        batch_size=len(items),
        queued_count=0,
        processing_count=0,
        completed_count=max(accepted, len(items)),
        failed_count=failed,
        duplicate_count=duplicate,
        rejected_count=rejected,
        created_at=created_at,
        completed_at=updated_at,
        updated_at=updated_at,
        created_by=0,
        metadata=metadata,
        items=ingest_items,
        events=[],
    )


def to_ingest_run_from_status(status: TrainingBatchStatusResponse) -> IngestRunResponse:
    batch_row = status.batch
    items = status.items
    metadata = dict(batch_row.progress or {})
    total_char_count = sum(int(item.char_count or 0) for item in items)
    if total_char_count > 0:
        metadata["total_char_count"] = total_char_count
    ingest_items = [
        IngestItemResponse(
            id=item.id,
            ingest_run_id=batch_row.id,
            corpus_uuid=batch_row.knowledge_base_id,
            queue_order=index,
            input_type=item.input_type,
            display_name=item.title or item.input_type,
            title=item.title,
            status=str(item.status),
            error_code=str(item.error_code) if item.error_code else None,
            error_message=item.error_message,
            created_at=batch_row.created_at,
            updated_at=batch_row.completed_at or batch_row.created_at,
            metadata={"char_count": item.char_count} if item.char_count is not None else {},
        )
        for index, item in enumerate(items)
    ]
    completed_count = int(batch_row.accepted_count or 0)
    if str(batch_row.status) in (
        TrainingBatchStatus.COMPLETED.value,
        TrainingBatchStatus.PARTIAL_SUCCESS.value,
    ):
        completed_count = max(completed_count, 1)
    return IngestRunResponse(
        id=batch_row.id,
        corpus_uuid=batch_row.knowledge_base_id,
        input_channel=batch_row.input_channel,
        status=str(batch_row.status),
        batch_size=int(batch_row.batch_size or 0),
        completed_count=completed_count,
        failed_count=int(batch_row.failed_count or 0),
        duplicate_count=int(batch_row.duplicate_count or 0),
        rejected_count=int(batch_row.rejected_count or 0),
        created_at=batch_row.created_at,
        completed_at=batch_row.completed_at,
        updated_at=batch_row.completed_at or batch_row.created_at,
        metadata=metadata,
        items=ingest_items,
        events=[],
    )


__all__ = [
    "to_ingest_run_from_status",
    "to_ingest_run_response",
    "to_synthetic_ingest_run_from_items",
]
