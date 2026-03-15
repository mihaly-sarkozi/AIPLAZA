from __future__ import annotations

import pytest

from apps.knowledge.application.structural_chunker import build_structural_chunks

pytestmark = pytest.mark.unit


def test_structural_chunker_builds_chunks():
    sentences = [
        {"id": 1, "sanitized_text": "a " * 120, "token_count": 120},
        {"id": 2, "sanitized_text": "b " * 120, "token_count": 120},
        {"id": 3, "sanitized_text": "c " * 120, "token_count": 120},
    ]
    chunks = build_structural_chunks(sentences, min_tokens=100, target_tokens=180, max_tokens=260, overlap_ratio=0.1)
    assert len(chunks) >= 1
    assert "sentence_ids" in chunks[0]
    assert "assertion_ids" in chunks[0]
    assert "entity_ids" in chunks[0]
