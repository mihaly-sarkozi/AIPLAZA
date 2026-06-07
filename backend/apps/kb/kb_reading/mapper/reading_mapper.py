from __future__ import annotations

from apps.kb.kb_reading.domain.ReadEvent import ReadEvent
from apps.kb.kb_reading.domain.ReadItem import ReadItem
from apps.kb.kb_reading.domain.ReadItemStatus import ReadItemStatus
from apps.kb.kb_reading.domain.ReadRun import ReadRun
from apps.kb.kb_reading.domain.ReadRunStatus import ReadRunStatus
from apps.kb.kb_reading.domain.ReadingErrorCode import ReadingErrorCode
from apps.kb.kb_reading.orm.ReadingBatch import ReadingBatch
from apps.kb.kb_reading.orm.ReadingEvent import ReadingEvent
from apps.kb.kb_reading.orm.ReadingItem import ReadingItem


def _parse_run_status(value: str) -> ReadRunStatus:
    try:
        return ReadRunStatus(value)
    except ValueError:
        return ReadRunStatus.FAILED


def _parse_item_status(value: str) -> ReadItemStatus:
    try:
        return ReadItemStatus(value)
    except ValueError:
        return ReadItemStatus.FAILED


def _parse_error_code(value: str | None) -> ReadingErrorCode | None:
    if not value:
        return None
    try:
        return ReadingErrorCode(value)
    except ValueError:
        return ReadingErrorCode.INTERNAL_ERROR


def read_run_to_domain(row: ReadingBatch) -> ReadRun:
    return ReadRun(
        id=row.id,
        tenant=row.tenant,
        knowledge_base_id=row.knowledge_base_id,
        input_channel=row.input_channel,
        status=_parse_run_status(row.status),
        batch_size=int(row.batch_size or 0),
        queued_count=int(row.queued_count or 0),
        failed_count=int(row.failed_count or 0),
        rejected_count=int(row.rejected_count or 0),
        duplicate_count=int(row.duplicate_count or 0),
        created_by=int(row.created_by),
        created_at=row.created_at,
        completed_at=row.completed_at,
        metadata=dict(row.metadata_json or {}),
    )


def read_run_to_orm(run: ReadRun) -> ReadingBatch:
    return ReadingBatch(
        id=run.id,
        tenant=run.tenant,
        knowledge_base_id=run.knowledge_base_id,
        input_channel=run.input_channel,
        status=run.status.value,
        batch_size=run.batch_size,
        queued_count=run.queued_count,
        failed_count=run.failed_count,
        rejected_count=run.rejected_count,
        duplicate_count=run.duplicate_count,
        created_by=run.created_by,
        created_at=run.created_at,
        completed_at=run.completed_at,
        metadata_json=dict(run.metadata or {}),
    )


def apply_run_to_orm(run: ReadRun, row: ReadingBatch) -> None:
    row.tenant = run.tenant
    row.knowledge_base_id = run.knowledge_base_id
    row.input_channel = run.input_channel
    row.status = run.status.value
    row.batch_size = run.batch_size
    row.queued_count = run.queued_count
    row.failed_count = run.failed_count
    row.rejected_count = run.rejected_count
    row.duplicate_count = run.duplicate_count
    row.created_by = run.created_by
    row.completed_at = run.completed_at
    row.metadata_json = dict(run.metadata or {})


def read_item_to_domain(row: ReadingItem) -> ReadItem:
    return ReadItem(
        id=row.id,
        read_run_id=row.reading_batch_id,
        knowledge_base_id=row.knowledge_base_id,
        input_type=row.input_type,
        title=row.title or "",
        status=_parse_item_status(row.status),
        raw_ref=row.raw_ref,
        content_hash=row.content_hash,
        idempotency_key=row.idempotency_key,
        error_code=_parse_error_code(row.error_code),
        error_message=row.error_message,
        retryable=bool(row.retryable),
        retry_count=int(row.retry_count or 0),
        duplicate_of_item_id=row.duplicate_of_item_id,
        original_filename=row.original_filename,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        origin_url=row.origin_url,
        final_url=row.final_url,
        status_code=row.status_code,
        metadata=dict(row.metadata_json or {}),
    )


def read_item_to_orm(item: ReadItem) -> ReadingItem:
    return ReadingItem(
        id=item.id,
        reading_batch_id=item.read_run_id,
        knowledge_base_id=item.knowledge_base_id,
        input_type=item.input_type,
        title=item.title,
        status=item.status.value,
        raw_ref=item.raw_ref,
        content_hash=item.content_hash,
        idempotency_key=item.idempotency_key,
        error_code=item.error_code.value if item.error_code is not None else None,
        error_message=item.error_message,
        retryable=item.retryable,
        retry_count=item.retry_count,
        duplicate_of_item_id=item.duplicate_of_item_id,
        original_filename=item.original_filename,
        mime_type=item.mime_type,
        size_bytes=item.size_bytes,
        origin_url=item.origin_url,
        final_url=item.final_url,
        status_code=item.status_code,
        metadata_json=dict(item.metadata or {}),
    )


def apply_item_to_orm(item: ReadItem, row: ReadingItem) -> None:
    row.reading_batch_id = item.read_run_id
    row.knowledge_base_id = item.knowledge_base_id
    row.input_type = item.input_type
    row.title = item.title
    row.status = item.status.value
    row.raw_ref = item.raw_ref
    row.content_hash = item.content_hash
    row.idempotency_key = item.idempotency_key
    row.error_code = item.error_code.value if item.error_code is not None else None
    row.error_message = item.error_message
    row.retryable = item.retryable
    row.retry_count = item.retry_count
    row.duplicate_of_item_id = item.duplicate_of_item_id
    row.original_filename = item.original_filename
    row.mime_type = item.mime_type
    row.size_bytes = item.size_bytes
    row.origin_url = item.origin_url
    row.final_url = item.final_url
    row.status_code = item.status_code
    row.metadata_json = dict(item.metadata or {})


def read_event_to_domain(row: ReadingEvent) -> ReadEvent:
    return ReadEvent(
        id=row.id,
        read_run_id=row.reading_batch_id,
        read_item_id=row.reading_item_id,
        event_type=row.event_type,
        message=row.message or "",
        details=dict(row.details_json or {}),
        created_at=row.created_at,
    )


def read_event_to_orm(event: ReadEvent) -> ReadingEvent:
    return ReadingEvent(
        id=event.id,
        reading_batch_id=event.read_run_id,
        reading_item_id=event.read_item_id,
        event_type=event.event_type,
        message=event.message,
        details_json=dict(event.details or {}),
        created_at=event.created_at,
    )


__all__ = [
    "apply_item_to_orm",
    "apply_run_to_orm",
    "read_event_to_domain",
    "read_event_to_orm",
    "read_item_to_domain",
    "read_item_to_orm",
    "read_run_to_domain",
    "read_run_to_orm",
]
