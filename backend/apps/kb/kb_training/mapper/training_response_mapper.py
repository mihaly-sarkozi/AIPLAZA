from __future__ import annotations

# backend/apps/kb/kb_training/mapper/training_response_mapper.py
# Feladat: ORM rekordok → vékony training API válasz DTO-k.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_training.dto.TrainingBatchSummaryResponse import TrainingBatchSummaryResponse
from apps.kb.kb_training.dto.TrainingItemSummaryResponse import TrainingItemSummaryResponse
from apps.kb.kb_training.dto.TrainingSubmitResponse import TrainingSubmitResponse
from apps.kb.kb_training.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_training.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_training.enums.TrainingItemStatus import TrainingItemStatus
from apps.kb.kb_training.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_training.orm.TrainingItem import TrainingItem


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


def to_item_summary_response(row: TrainingItem) -> TrainingItemSummaryResponse:
    metadata = dict(row.metadata_json or {})
    char_count = metadata.get("char_count")
    parsed_char_count = int(char_count) if isinstance(char_count, int) else None
    return TrainingItemSummaryResponse(
        id=row.id,
        input_type=row.input_type,
        title=row.title or "",
        status=_parse_item_status(row.status),
        error_code=_parse_error_code(row.error_code),
        error_message=row.error_message,
        char_count=parsed_char_count,
    )


def to_submit_response(
    *,
    batch_id: str,
    status: TrainingBatchStatus,
    items: list[TrainingItem] | None = None,
) -> TrainingSubmitResponse:
    item_rows = list(items or [])
    summaries = [to_item_summary_response(item) for item in item_rows]
    batch_size = len(summaries) if summaries else 1
    accepted_count = sum(1 for item in summaries if item.status == TrainingItemStatus.ACCEPTED.value)
    failed_count = sum(1 for item in summaries if item.status == TrainingItemStatus.FAILED.value)
    duplicate_count = sum(1 for item in summaries if str(item.status) == "duplicate")
    rejected_count = sum(1 for item in summaries if item.status == TrainingItemStatus.REJECTED.value)
    include_items = batch_size > 1 or failed_count > 0 or duplicate_count > 0 or rejected_count > 0
    return TrainingSubmitResponse(
        batch_id=batch_id,
        status=status,
        batch_size=batch_size,
        accepted_count=accepted_count or (1 if status == TrainingBatchStatus.COMPLETED and not include_items else 0),
        failed_count=failed_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        items=summaries if include_items else [],
    )


__all__ = [
    "to_batch_summary_response",
    "to_item_summary_response",
    "to_submit_response",
]
