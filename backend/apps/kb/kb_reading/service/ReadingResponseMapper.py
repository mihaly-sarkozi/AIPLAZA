from __future__ import annotations

# backend/apps/kb/kb_reading/service/ReadingResponseMapper.py
# Feladat: Domain → DTO leképezés a HTTP válaszokhoz.
# Sárközi Mihály - 2026.06.07

import mimetypes
from shared.utils.clock import utc_now
from urllib.parse import quote

from apps.kb.kb_reading.domain.ReadEvent import ReadEvent
from apps.kb.kb_reading.domain.ReadItem import ReadItem
from apps.kb.kb_reading.domain.ReadRun import ReadRun
from apps.kb.kb_reading.dto.ReadEventResponse import ReadEventResponse
from apps.kb.kb_reading.dto.ReadItemResponse import ReadItemResponse
from apps.kb.kb_reading.dto.ReadRunResponse import ReadRunResponse
from apps.kb.kb_reading.ports.ReadingRepository import ReadingRepository


def content_disposition_filename(filename: str) -> str:
    """Összeállítja a letöltési fájlnevet."""
    return f"inline; filename*=UTF-8''{quote(filename)}"


def find_item_by_id(repository: ReadingRepository, item_id: str) -> ReadItem | None:
    """Item keresése azonosító alapján."""
    return repository.get_item(item_id)


def to_run_response(run: ReadRun) -> ReadRunResponse:
    """ReadRun domain modell DTO-vá alakítása."""
    return ReadRunResponse(
        id=run.id,
        tenant=run.tenant,
        knowledge_base_id=run.knowledge_base_id,
        input_channel=run.input_channel,
        status=run.status,
        batch_size=run.batch_size,
        queued_count=run.queued_count,
        failed_count=run.failed_count,
        rejected_count=run.rejected_count,
        duplicate_count=run.duplicate_count,
        created_by=run.created_by,
        created_at=run.created_at,
        completed_at=run.completed_at,
        metadata=dict(run.metadata or {}),
    )


def to_item_response(item: ReadItem) -> ReadItemResponse:
    """ReadItem domain modell DTO-vá alakítása."""
    return ReadItemResponse(
        id=item.id,
        read_run_id=item.read_run_id,
        knowledge_base_id=item.knowledge_base_id,
        input_type=item.input_type,
        title=item.title,
        status=item.status,
        raw_ref=item.raw_ref,
        content_hash=item.content_hash,
        idempotency_key=item.idempotency_key,
        error_code=item.error_code,
        error_message=item.error_message,
        retryable=item.retryable,
        retry_count=item.retry_count,
        duplicate_of_item_id=item.duplicate_of_item_id,
        metadata=dict(item.metadata or {}),
    )


def to_event_response(event: ReadEvent) -> ReadEventResponse:
    """ReadEvent domain modell DTO-vá alakítása."""
    return ReadEventResponse(
        id=event.id,
        read_run_id=event.read_run_id,
        read_item_id=event.read_item_id,
        event_type=event.event_type,
        message=event.message,
        details=dict(event.details or {}),
        created_at=event.created_at or utc_now(),
    )


def resolve_media_type(item: ReadItem) -> str:
    """Nyers tartalom media type meghatározása."""
    if item.mime_type:
        return str(item.mime_type)
    metadata = dict(item.metadata or {})
    content_type = metadata.get("content_type") or metadata.get("mime_type")
    if content_type:
        return str(content_type)
    if item.input_type == "text":
        return "text/plain; charset=utf-8"
    if item.input_type == "url":
        return "application/octet-stream"
    guessed, _encoding = mimetypes.guess_type(str(metadata.get("filename") or item.title or ""))
    return guessed or "application/octet-stream"


def resolve_filename(item: ReadItem) -> str:
    """Nyers tartalom fájlnév meghatározása."""
    metadata = dict(item.metadata or {})
    if item.original_filename:
        return str(item.original_filename)
    if item.input_type == "text":
        return "text.txt"
    if metadata.get("title"):
        return str(metadata["title"])
    if item.input_type == "url":
        return "url_response.bin"
    filename = metadata.get("filename")
    if filename:
        return str(filename)
    return item.title or "download.bin"


__all__ = [
    "content_disposition_filename",
    "find_item_by_id",
    "resolve_filename",
    "resolve_media_type",
    "to_event_response",
    "to_item_response",
    "to_run_response",
]
