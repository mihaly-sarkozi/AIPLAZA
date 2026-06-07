from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadItem.py
# Feladat: Egy beolvasási elem modellje (állapot + bemenet meta együtt).
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_reading.domain.ReadItemStatus import ReadItemStatus
from apps.kb.kb_reading.domain.ReadingErrorCode import ReadingErrorCode


@dataclass
class ReadItem:
    """Egy beolvasási elem adatai, állapota és bemenet metaadatai."""

    id: str
    read_run_id: str
    knowledge_base_id: str
    input_type: str
    title: str
    status: ReadItemStatus
    raw_ref: str | None
    content_hash: str | None
    idempotency_key: str | None
    error_code: ReadingErrorCode | None
    error_message: str | None
    retryable: bool
    retry_count: int
    duplicate_of_item_id: str | None
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    origin_url: str | None = None
    final_url: str | None = None
    status_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ReadItem"]
