from __future__ import annotations

# backend/apps/kb/kb_ingest/mapper/training_response_mapper.py
# Feladat: ORM rekordok → vékony training API válasz DTO-k.
# Sárközi Mihály - 2026.06.07

from datetime import datetime

from apps.kb.kb_ingest.dto.TrainingBatchStatusResponse import TrainingBatchStatusResponse
from apps.kb.kb_ingest.dto.TrainingBatchSummaryResponse import TrainingBatchSummaryResponse
from apps.kb.kb_ingest.dto.TrainingItemSummaryResponse import TrainingItemSummaryResponse
from apps.kb.kb_ingest.dto.TrainingTextResponse import TrainingTextResponse
from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.enums.TrainingItemStatus import TrainingItemStatus
from apps.kb.kb_ingest.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_ingest.orm.TrainingItem import TrainingItem


def _parse_batch_status(value: str) -> TrainingBatchStatus:
    try:
        return TrainingBatchStatus(value)
    except ValueError:
        return TrainingBatchStatus.FAILED


def _parse_item_status(value: str) -> TrainingItemStatus:
    try:
        return TrainingItemStatus(value)
    except ValueError:
        return TrainingItemStatus.FAILED


def _parse_error_code(value: str | None) -> TrainingErrorCode | None:
    if not value:
        return None
    try:
        return TrainingErrorCode(value)
    except ValueError:
        return TrainingErrorCode.INTERNAL_ERROR


def _accepted_item_count(items: list[TrainingItem]) -> int:
    return sum(1 for item in items if item.status == TrainingItemStatus.ACCEPTED.value)


def to_batch_summary_response(row: TrainingBatch, *, items: list[TrainingItem]) -> TrainingBatchSummaryResponse:
    metadata = dict(row.metadata_json or {})
    progress = metadata.get("progress_summary")
    if not isinstance(progress, dict):
        progress = None
    return TrainingBatchSummaryResponse(
        id=row.id,
        knowledge_base_id=row.knowledge_base_id,
        input_channel=row.input_channel,
        status=_parse_batch_status(row.status),
        batch_size=int(row.batch_size or 0),
        accepted_count=_accepted_item_count(items),
        failed_count=int(row.failed_count or 0),
        rejected_count=int(row.rejected_count or 0),
        duplicate_count=int(row.duplicate_count or 0),
        created_at=row.created_at,
        completed_at=row.completed_at,
        progress=progress,
    )


def _parse_char_count(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def to_item_summary_response(row: TrainingItem) -> TrainingItemSummaryResponse:
    metadata = dict(row.metadata_json or {})
    parsed_char_count = _parse_char_count(metadata.get("char_count"))
    return TrainingItemSummaryResponse(
        id=row.id,
        input_type=row.input_type,
        title=row.title or "",
        status=_parse_item_status(row.status),
        error_code=_parse_error_code(row.error_code),
        error_message=row.error_message,
        char_count=parsed_char_count,
    )


def to_text_response(
    *,
    batch_id: str,
    status: TrainingBatchStatus,
    created_at: datetime,
    completed_at: datetime | None = None,
    items: list[TrainingItem] | None = None,
) -> TrainingTextResponse:
    item_rows = list(items or [])
    summaries = [to_item_summary_response(item) for item in item_rows]
    batch_size = len(summaries) if summaries else 1
    accepted_count = sum(1 for item in summaries if item.status == TrainingItemStatus.ACCEPTED.value)
    failed_count = sum(1 for item in summaries if item.status == TrainingItemStatus.FAILED.value)
    duplicate_count = sum(1 for item in summaries if str(item.status) == "duplicate")
    rejected_count = sum(1 for item in summaries if item.status == TrainingItemStatus.REJECTED.value)
    return TrainingTextResponse(
        batch_id=batch_id,
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        batch_size=batch_size,
        accepted_count=accepted_count or (1 if status == TrainingBatchStatus.COMPLETED and batch_size == 1 else 0),
        failed_count=failed_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        items=summaries,
    )


def to_text_response_from_batch_status(status: TrainingBatchStatusResponse) -> TrainingTextResponse:
    batch = status.batch
    summaries = list(status.items)
    batch_size = len(summaries) if summaries else max(int(batch.batch_size or 0), 1)
    accepted_count = int(batch.accepted_count or 0)
    return TrainingTextResponse(
        batch_id=batch.id,
        status=batch.status,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        batch_size=batch_size,
        accepted_count=accepted_count or (1 if batch.status == TrainingBatchStatus.COMPLETED else 0),
        failed_count=int(batch.failed_count or 0),
        duplicate_count=int(batch.duplicate_count or 0),
        rejected_count=int(batch.rejected_count or 0),
        items=summaries,
    )


__all__ = [
    "to_batch_summary_response",
    "to_item_summary_response",
    "to_text_response",
    "to_text_response_from_batch_status",
]
