from __future__ import annotations

# backend/apps/kb/kb_reading/dto/item.py
# Feladat: Elem adatok séma a válaszokban.
# Sárközi Mihály - 2026.06.07

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.kb.kb_reading.domain.ReadItemStatus import ReadItemStatus
from apps.kb.kb_reading.domain.ReadingErrorCode import ReadingErrorCode


class ReadItemResponse(BaseModel):
    """Adatátviteli séma a kérés vagy válasz mezőihez."""
    model_config = ConfigDict(use_enum_values=True)

    id: str
    read_run_id: str
    knowledge_base_id: str
    input_type: str
    title: str
    status: ReadItemStatus
    raw_ref: str | None = None
    content_hash: str | None = None
    idempotency_key: str | None = None
    error_code: ReadingErrorCode | None = None
    error_message: str | None = None
    retryable: bool = False
    retry_count: int = 0
    duplicate_of_item_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["ReadItemResponse"]
