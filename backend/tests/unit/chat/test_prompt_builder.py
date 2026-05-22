from __future__ import annotations

import pytest

from apps.chat.service.prompt_builder import PromptBuilder

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _builder() -> PromptBuilder:
    return PromptBuilder(
        max_conversation_history_messages=4,
        max_conversation_history_chars=1000,
        max_retrieval_history_items=3,
        max_retrieval_history_chars=600,
        multi_kb_packet_score_threshold=0.45,
        multi_kb_block_score_threshold=0.35,
        multi_kb_block_relative_floor_ratio=0.8,
    )


def test_build_messages_includes_policy_history_context_and_user_question() -> None:
    messages = _builder().build_messages(
        question="Mi a státusz?",
        context_text="Context chunks:\n- A szerződés aktív.",
        conversation_history=[{"role": "user", "content": "Korábbi kérdés"}],
        retrieval_history=["A szerződés aktív."],
        pii_prompt_policy="PII policy active.",
        brand_voice="Legyen tömör, bizalmi hangvétel.",
        channel_settings={"channel": "api", "max_sentences": 4},
        safety_constraints="Ne találj ki forrást.",
        citation_context="source-1, source-2",
    )

    assert messages[0]["role"] == "system"
    assert any("PII policy active" in item["content"] for item in messages)
    assert any("Brand voice irányelv" in item["content"] for item in messages)
    assert any("Channel beállítások" in item["content"] for item in messages)
    assert any("Safety szabályok" in item["content"] for item in messages)
    assert any("Citation context" in item["content"] for item in messages)
    assert any("Beszélgetési előzmény" in item["content"] for item in messages)
    assert any("Korábbi kérdésekből" in item["content"] for item in messages)
    assert messages[-1] == {"role": "user", "content": "Mi a státusz?"}


def test_prompt_context_payload_exposes_index_debug_thresholds() -> None:
    payload = _builder().build_prompt_context_payload(
        question="Mi a státusz?",
        messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "Mi a státusz?"}],
        conversation_history=None,
        retrieval_history=None,
        packet={
            "answer_mode": "summary",
            "retrieval_confidence": 0.5,
            "context_blocks": [
                {
                    "block_id": "b1",
                    "source_id": "s1",
                    "subject": "contract",
                    "snippet": "A szerződés aktív.",
                    "match_score": 0.7,
                }
            ],
        },
        context_text="Context chunks:\n- A szerződés aktív.",
    )

    assert payload["informational_prompt"] == "system"
    assert payload["latest_hits"][0]["block_id"] == "b1"
    assert payload["index_debug"]["retrieval_confidence"] == 0.5
    assert payload["index_debug"]["thresholds"]["packet_score_threshold"] == 0.45
