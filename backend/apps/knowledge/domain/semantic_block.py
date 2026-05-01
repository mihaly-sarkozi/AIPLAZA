from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


SEMANTIC_BLOCK_BUILDER_VERSION = "semantic_block_builder_v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SemanticBlock:
    id: str = field(default_factory=lambda: str(uuid4()))
    corpus_uuid: str = ""
    source_id: str = ""
    document_id: str = ""
    paragraph_ids: list[str] = field(default_factory=list)
    sentence_ids: list[str] = field(default_factory=list)
    claim_ids: list[str] = field(default_factory=list)
    order_start: int = 0
    order_end: int = 0
    primary_subject: str = ""
    subject_key: str = ""
    primary_space: str = ""
    space_key: str = ""
    primary_time: str = ""
    time_key: str = ""
    topic_key: str = ""
    block_type: str = "semantic_unit"
    text: str = ""
    summary: str = ""
    predicates: list[str] = field(default_factory=list)
    entity_keys: list[str] = field(default_factory=list)
    space_modes: list[str] = field(default_factory=list)
    space_values: list[str] = field(default_factory=list)
    time_modes: list[str] = field(default_factory=list)
    time_values: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=_utcnow)
    builder_version: str = SEMANTIC_BLOCK_BUILDER_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


def semantic_block_to_json_dict(block: SemanticBlock) -> dict[str, Any]:
    return {
        "id": block.id,
        "corpus_uuid": block.corpus_uuid,
        "source_id": block.source_id,
        "document_id": block.document_id,
        "paragraph_ids": list(block.paragraph_ids),
        "sentence_ids": list(block.sentence_ids),
        "claim_ids": list(block.claim_ids),
        "order_start": block.order_start,
        "order_end": block.order_end,
        "primary_subject": block.primary_subject,
        "subject_key": block.subject_key,
        "primary_space": block.primary_space,
        "space_key": block.space_key,
        "primary_time": block.primary_time,
        "time_key": block.time_key,
        "topic_key": block.topic_key,
        "block_type": block.block_type,
        "text": block.text,
        "summary": block.summary,
        "predicates": list(block.predicates),
        "entity_keys": list(block.entity_keys),
        "space_modes": list(block.space_modes),
        "space_values": list(block.space_values),
        "time_modes": list(block.time_modes),
        "time_values": list(block.time_values),
        "confidence": round(float(block.confidence or 0.0), 4),
        "created_at": block.created_at.isoformat(),
        "builder_version": block.builder_version,
        "metadata": dict(block.metadata or {}),
    }


__all__ = ["SEMANTIC_BLOCK_BUILDER_VERSION", "SemanticBlock", "semantic_block_to_json_dict"]
