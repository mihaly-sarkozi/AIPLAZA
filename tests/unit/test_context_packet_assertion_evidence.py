from __future__ import annotations

import pytest

from apps.knowledge.application.context_builder import KnowledgeContextBuilder

pytestmark = pytest.mark.unit


def test_context_packet_contains_assertions_with_evidence():
    builder = KnowledgeContextBuilder()
    packet = builder.build_context_packet(
        assertion_hits=[
            {
                "id": "assertion-11",
                "text": "A állítás",
                "semantic_match": 0.8,
                "entity_match": 0.8,
                "time_match": 0.8,
                "place_match": 0.8,
                "graph_proximity": 0.8,
                "strength": 0.8,
                "confidence": 0.8,
                "recency": 0.8,
            }
        ],
        sentence_hits=[
            {
                "id": "sentence-5",
                "text": "Bizonyító mondat",
                "assertion_ids": ["assertion-11"],
                "semantic_match": 0.7,
                "entity_match": 0.7,
                "time_match": 0.7,
                "place_match": 0.7,
                "graph_proximity": 0.7,
                "strength": 0.7,
                "confidence": 0.7,
                "recency": 0.7,
            }
        ],
        chunk_hits=[],
    )
    assert len(packet["top_assertions"]) == 1
    assert len(packet["evidence_sentences"]) == 1
    assert packet["evidence_sentences"][0]["id"] == "sentence-5"
