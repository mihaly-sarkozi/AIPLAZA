from __future__ import annotations

import pytest

from apps.knowledge.application.reranker import compute_final_score, compute_time_overlap_score

pytestmark = pytest.mark.unit


def test_context_reranker_uses_composite_signal():
    low_semantic_high_strength = compute_final_score(
        {
            "semantic_match": 0.3,
            "entity_match": 0.6,
            "time_match": 0.2,
            "place_match": 0.1,
            "graph_proximity": 0.4,
            "strength": 0.9,
            "confidence": 0.8,
            "recency": 0.7,
        }
    )
    high_semantic_low_other = compute_final_score(
        {
            "semantic_match": 0.9,
            "entity_match": 0.0,
            "time_match": 0.0,
            "place_match": 0.0,
            "graph_proximity": 0.0,
            "strength": 0.0,
            "confidence": 0.0,
            "recency": 0.0,
        }
    )
    assert low_semantic_high_strength > 0.0
    assert high_semantic_low_other > 0.0


def test_time_overlap_affects_reranking():
    overlap = compute_time_overlap_score(
        query_from="2024-01-01T00:00:00",
        query_to="2024-12-31T23:59:59",
        item_from="2024-03-01T00:00:00",
        item_to="2024-05-01T00:00:00",
    )
    no_overlap = compute_time_overlap_score(
        query_from="2024-01-01T00:00:00",
        query_to="2024-12-31T23:59:59",
        item_from="2022-01-01T00:00:00",
        item_to="2022-02-01T00:00:00",
    )
    assert overlap > no_overlap
