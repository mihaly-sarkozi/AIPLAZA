from __future__ import annotations

import pytest

from apps.knowledge.application.indexing_pipeline import KnowledgeIndexingPipeline

pytestmark = pytest.mark.unit


class _Dummy:
    pass


def test_chunk_builder_preserves_sentence_order():
    pipeline = KnowledgeIndexingPipeline(repo=_Dummy(), vector_index=_Dummy(), extractor=None)
    sentences = [
        {"id": 1, "sanitized_text": "Első mondat.", "token_count": 120},
        {"id": 2, "sanitized_text": "Második mondat.", "token_count": 130},
        {"id": 3, "sanitized_text": "Harmadik mondat.", "token_count": 140},
        {"id": 4, "sanitized_text": "Negyedik mondat.", "token_count": 160},
    ]
    chunks = pipeline.build_structural_chunks(sentences, min_tokens=200, target_tokens=260, max_tokens=320)
    assert len(chunks) >= 2
    assert chunks[0]["sentence_ids"][0] == 1
    assert all(ch["token_count"] > 0 for ch in chunks)


def test_sentence_split_handles_basic_text():
    pipeline = KnowledgeIndexingPipeline(repo=_Dummy(), vector_index=_Dummy(), extractor=None)
    out = pipeline.split_sentences("Ez az első. Ez a második! Ez a harmadik?")
    assert len(out) == 3
