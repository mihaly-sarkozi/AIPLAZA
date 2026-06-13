"""Parent chunk hash determinisztikus azonosító."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.chunk.parent_chunk_hash import compute_parent_chunk_hash

pytestmark = pytest.mark.unit


def test_parent_chunk_hash_is_deterministic() -> None:
    kwargs = {
        "training_item_id": "training_item_1",
        "heading_path": ["Fejezet", "Alfejezet"],
        "section_title": "Alfejezet",
        "source_part_ids": ["und_part_2", "und_part_1"],
    }
    first = compute_parent_chunk_hash(**kwargs)
    second = compute_parent_chunk_hash(**kwargs)
    assert first == second
    assert len(first) == 64


def test_parent_chunk_hash_changes_when_sources_change() -> None:
    base = {
        "training_item_id": "training_item_1",
        "heading_path": ["Fejezet"],
        "section_title": "Fejezet",
        "source_part_ids": ["und_part_1"],
    }
    other = dict(base)
    other["source_part_ids"] = ["und_part_2"]
    assert compute_parent_chunk_hash(**base) != compute_parent_chunk_hash(**other)
