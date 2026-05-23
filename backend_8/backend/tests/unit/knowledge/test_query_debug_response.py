from __future__ import annotations

import pytest

from apps.knowledge.api.router import _query_debug_payload


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_query_debug_payload_marks_response_answer_presence() -> None:
    response = {
        "metadata": {"synthesis_called": True},
        "query_profile": {"intent": "state"},
        "matched_chunks": [{"entity_name": "London office"}],
        "matched_claims": [{"claim_id": "c-current"}],
        "answer_text": "The London office is currently inactive.",
        "answer_mode": "direct",
    }

    payload = _query_debug_payload(
        endpoint_called="/knowledge/retrieve",
        query_text="What is the status of London office?",
        response=response,
    )

    assert payload == {
        "endpoint_called": "/knowledge/retrieve",
        "query_text": "What is the status of London office?",
        "query_profile": {"intent": "state"},
        "matched_chunks_count": 1,
        "matched_claims_count": 1,
        "conflict_marker_included": False,
        "temporal_context_used": False,
        "synthesis_called": True,
        "answer_text": "The London office is currently inactive.",
        "answer_mode": "direct",
        "cited_claim_ids": [],
        "cited_sentence_ids": [],
        "cited_source_ids": [],
        "evidence": [],
        "explanation": {},
        "response_contains_answer_text": True,
    }
    assert response["query_debug"] == payload
    assert response["metadata"]["query_debug"] == payload


def test_query_debug_payload_exposes_empty_answer_with_matches() -> None:
    response = {
        "metadata": {"synthesis_called": True},
        "query_profile": {"intent": "state"},
        "matched_chunks": [{"entity_name": "London office"}],
        "matched_claims": [],
        "answer_text": "",
        "answer_mode": "no_answer",
    }

    payload = _query_debug_payload(
        endpoint_called="/knowledge/chat-context",
        query_text="What is the status of London office?",
        response=response,
    )

    assert payload["matched_chunks_count"] == 1
    assert payload["answer_text"] == ""
    assert payload["response_contains_answer_text"] is False
