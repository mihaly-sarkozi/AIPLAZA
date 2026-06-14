from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingDiscoveryBundleDto:
    chunk_id: str
    language_code: str | None = None
    content_type: str | None = None
    section_title: str | None = None
    heading_path: str | None = None
    keywords: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    process_steps: tuple[str, ...] = ()


__all__ = ["EmbeddingDiscoveryBundleDto"]
