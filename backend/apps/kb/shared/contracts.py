from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaterialRef:
    material_id: str
    knowledge_base_id: str
    raw_ref: str
    content_type: str


@dataclass
class SearchContextItem:
    chunk_id: str
    source_id: str | None
    text: str
    score: float


@dataclass(frozen=True)
class IngestItemSnapshot:
    """Ingest item olvasási nézet a megértési pipeline számára (modulhatáron átadott contract)."""

    item_id: str
    training_batch_id: str
    knowledge_base_id: str
    status: str
    raw_ref: str | None
    mime_type: str | None
    input_type: str
    original_filename: str | None
    title: str
    content_hash: str | None


__all__ = ["IngestItemSnapshot", "MaterialRef", "SearchContextItem"]
