from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/UnderstandingJobContext.py
# Feladat: A pipeline lépések közös kontextusa — azonosítók + forrás metaadatok.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderstandingJobContext:
    job_id: str
    training_item_id: str
    training_batch_id: str
    knowledge_base_id: str
    tenant_slug: str | None
    created_by: int | None
    raw_ref: str
    mime_type: str | None
    source_type: str
    file_name: str | None
    title: str
    content_hash: str | None


__all__ = ["UnderstandingJobContext"]
