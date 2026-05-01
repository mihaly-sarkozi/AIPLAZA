from __future__ import annotations

from typing import Any


SEMANTIC_BLOCK_INDEX_VERSION = "semantic_block_index_v0"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list_text(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in out:
            out.append(text)
    return out


def _index_text(block: dict[str, Any]) -> str:
    subject = _text(block.get("primary_subject"))
    space = _text(block.get("primary_space") or ", ".join(_list_text(block.get("space_values"))))
    time = _text(block.get("primary_time") or ", ".join(_list_text(block.get("time_values"))))
    predicates = ", ".join(_list_text(block.get("predicates")))
    summary = _text(block.get("summary"))
    text = _text(block.get("text"))
    parts = [
        f"Alany: {subject}" if subject else "",
        f"Hely: {space}" if space else "",
        f"Idő: {time}" if time else "",
        f"Összefoglaló: {summary}" if summary else "",
        f"Állítások: {predicates}" if predicates else "",
        text,
    ]
    return "\n".join(part for part in parts if part)


def _metadata(block: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "block_id": block.get("id"),
        "corpus_uuid": block.get("corpus_uuid"),
        "source_id": block.get("source_id"),
        "document_id": block.get("document_id"),
        "paragraph_ids": _list_text(block.get("paragraph_ids")),
        "sentence_ids": _list_text(block.get("sentence_ids")),
        "claim_ids": _list_text(block.get("claim_ids")),
        "order_start": block.get("order_start"),
        "order_end": block.get("order_end"),
        "primary_subject": block.get("primary_subject"),
        "subject_key": block.get("subject_key"),
        "primary_space": block.get("primary_space"),
        "space_key": block.get("space_key"),
        "primary_time": block.get("primary_time"),
        "time_key": block.get("time_key"),
        "block_type": block.get("block_type"),
        "text": block.get("text"),
        "summary": block.get("summary"),
        "predicates": _list_text(block.get("predicates")),
        "entity_keys": _list_text(block.get("entity_keys")),
        "space_modes": _list_text(block.get("space_modes")),
        "space_values": _list_text(block.get("space_values")),
        "time_modes": _list_text(block.get("time_modes")),
        "time_values": _list_text(block.get("time_values")),
        "confidence": block.get("confidence"),
        "block_status": block.get("block_status"),
        "source_reliability": block.get("source_reliability"),
        "retrieval_weight": block.get("retrieval_weight"),
        "conflict_count": block.get("conflict_count"),
        "conflicts": list(block.get("conflicts") or []),
        "builder_version": block.get("builder_version"),
        "metadata": dict(block.get("metadata") or {}) if isinstance(block.get("metadata"), dict) else {},
    }
    return {key: value for key, value in metadata.items() if value not in (None, "", [])}


def build_semantic_block_index_rows(
    semantic_blocks: list[dict[str, Any]],
    *,
    build_id: str,
    index_profile_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in semantic_blocks:
        if not isinstance(block, dict):
            continue
        block_id = _text(block.get("id"))
        text = _index_text(block)
        if not block_id or not text:
            continue
        metadata = _metadata(block)
        rows.append(
            {
                "id": block_id,
                "text": text,
                "payload": {
                    "block_id": block_id,
                    "source_id": block.get("source_id"),
                    "document_id": block.get("document_id"),
                    "subject": block.get("primary_subject"),
                    "subject_key": block.get("subject_key"),
                    "space": block.get("primary_space"),
                    "space_key": block.get("space_key"),
                    "time": block.get("primary_time"),
                    "time_key": block.get("time_key"),
                    "time_modes": _list_text(block.get("time_modes")),
                    "space_modes": _list_text(block.get("space_modes")),
                    "entity_keys": _list_text(block.get("entity_keys")),
                    "block_status": block.get("block_status"),
                    "source_reliability": block.get("source_reliability"),
                    "retrieval_weight": block.get("retrieval_weight"),
                    "conflict_count": block.get("conflict_count"),
                    "claim_ids": _list_text(block.get("claim_ids")),
                    "sentence_ids": _list_text(block.get("sentence_ids")),
                    "metadata": metadata,
                    "text": text,
                    "raw_block_text": block.get("text"),
                    "build_id": build_id,
                    "index_profile_key": index_profile_key,
                },
            }
        )
    return rows


__all__ = ["SEMANTIC_BLOCK_INDEX_VERSION", "build_semantic_block_index_rows"]
