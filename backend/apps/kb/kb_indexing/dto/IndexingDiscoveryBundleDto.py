from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexingDiscoveryBundleDto:
    chunk_id: str
    language_code: str | None = None
    language_confidence: float | None = None
    content_type: str | None = None
    content_type_confidence: float | None = None
    section_title: str | None = None
    heading_path: str | None = None
    text_preview: str = ""
    page_numbers: list[int] = field(default_factory=list)
    source_part_ids: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    temporal_mentions: list[dict[str, Any]] = field(default_factory=list)
    spatial_mentions: list[dict[str, Any]] = field(default_factory=list)
    process_mentions: list[dict[str, Any]] = field(default_factory=list)
    overall_score: float | None = None
    score_components: dict[str, Any] = field(default_factory=dict)
    relationship_summary: list[dict[str, Any]] = field(default_factory=list)
    source_type: str | None = None
    document_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


__all__ = ["IndexingDiscoveryBundleDto"]
