from __future__ import annotations

import hashlib
import json


def compute_parent_chunk_hash(
    *,
    training_item_id: str,
    heading_path: list[str],
    section_title: str | None,
    source_part_ids: list[str],
) -> str:
    payload = json.dumps(
        {
            "training_item_id": training_item_id,
            "heading_path": list(heading_path or []),
            "section_title": section_title or "",
            "source_part_ids": sorted(part_id for part_id in source_part_ids if part_id),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parent_chunk_id_from_hash(parent_chunk_hash: str) -> str:
    return f"chunk_parent_{parent_chunk_hash[:32]}"


__all__ = ["compute_parent_chunk_hash", "parent_chunk_id_from_hash"]
