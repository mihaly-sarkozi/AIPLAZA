from __future__ import annotations

import pytest

from apps.knowledge.service.synthesis_engine_v0 import SynthesisEngineV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_synthesis_engine_answers_status_with_historical_context() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "London office", "intent": "state"},
        matched_chunks=[{"entity_name": "London office", "conflict_marker": False, "evidence_ids": ["e-current", "e-2024"]}],
        matched_claims=[
            {
                "entity_name": "London office",
                "claim_id": "c-current",
                "claim_text": "currently inactive",
                "state": "inactive",
                "time_filter": "current",
                "conflict_marker": False,
                "sentence_ids": ["s-current"],
                "source_ids": ["src-london"],
            },
            {
                "entity_name": "London office",
                "claim_id": "c-2024",
                "claim_text": "inactive in 2024",
                "state": "inactive",
                "time_filter": "historical",
                "conflict_marker": False,
                "sentence_ids": ["s-2024"],
                "source_ids": ["src-london"],
            },
        ],
    )

    assert result["answer_text"] == "The London office is currently inactive. Historically, it was inactive in 2024."
    assert result["answer_mode"] == "state_with_history"
    assert result["cited_claim_ids"] == ["c-current", "c-2024"]
    assert result["cited_evidence_ids"] == ["c-current", "c-2024", "s-current", "s-2024", "e-current", "e-2024"]


def test_synthesis_engine_does_not_leak_current_marker_into_historical_sentence() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "London office", "intent": "state"},
        matched_chunks=[{"entity_name": "London office", "conflict_marker": False}],
        matched_claims=[
            {
                "entity_name": "London office",
                "claim_id": "c-current",
                "claim_text": "currently inactive",
                "state": "inactive",
                "time_filter": "current",
                "conflict_marker": False,
                "sentence_ids": ["s-current"],
                "source_ids": ["src-london"],
            },
            {
                "entity_name": "London office",
                "claim_id": "c-2024",
                "claim_text": "inactive in 2024, currently",
                "state": "inactive",
                "time_filter": "historical",
                "conflict_marker": False,
                "sentence_ids": ["s-2024"],
                "source_ids": ["src-london"],
            },
        ],
    )

    assert result["answer_text"] == "The London office is currently inactive. Historically, it was inactive in 2024."
    assert result["answer_text"].count("currently") == 1
    assert "Historically, it was inactive in 2024, currently" not in result["answer_text"]


def test_synthesis_engine_keeps_current_fact_when_time_filter_is_missing() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "London office", "intent": "state"},
        matched_chunks=[{"entity_name": "London office", "conflict_marker": False}],
        matched_claims=[
            {
                "entity_name": "London office",
                "claim_id": "c-current",
                "claim_text": "currently inactive",
                "state": "inactive",
                "fact_bucket": "current",
                "conflict_marker": False,
                "sentence_ids": ["s-current"],
                "source_ids": ["src-london"],
            },
            {
                "entity_name": "London office",
                "claim_id": "c-2024",
                "claim_text": "inactive in 2024",
                "state": "inactive",
                "time_filter": "historical",
                "conflict_marker": False,
                "sentence_ids": ["s-2024"],
                "source_ids": ["src-london"],
            },
        ],
    )

    assert result["answer_text"] == "The London office is currently inactive. Historically, it was inactive in 2024."
    assert result["synthesis_debug"]["current_facts_count"] == 1
    assert result["synthesis_debug"]["historical_facts_count"] == 1
    assert result["synthesis_debug"]["raw_matched_claims"][0]["claim_id"] == "c-current"


def test_synthesis_engine_reports_conflicting_current_status_without_choosing_side() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "London office", "intent": "state"},
        matched_chunks=[{"entity_name": "London office", "conflict_marker": True, "evidence_ids": ["e-conflict"]}],
        matched_claims=[
            {
                "entity_name": "London office",
                "claim_id": "c-active",
                "claim_text": "currently active",
                "state": "active",
                "time_filter": "current",
                "conflict_marker": True,
                "sentence_ids": ["s-active"],
                "source_ids": ["src-london"],
            },
            {
                "entity_name": "London office",
                "claim_id": "c-inactive",
                "claim_text": "currently inactive",
                "state": "inactive",
                "time_filter": "current",
                "conflict_marker": True,
                "sentence_ids": ["s-inactive"],
                "source_ids": ["src-london"],
            },
            {
                "entity_name": "London office",
                "claim_id": "c-2024",
                "claim_text": "inactive in 2024",
                "state": "inactive",
                "time_filter": "historical",
                "conflict_marker": False,
                "sentence_ids": ["s-2024"],
                "source_ids": ["src-london"],
            },
        ],
    )

    assert result["answer_mode"] == "conflict"
    assert result["answer_text"] == (
        "The London office has conflicting current status information: one source says it is active, "
        "another says it is inactive. Historically, it was inactive in 2024."
    )
    assert result["synthesis_confidence"] > 0.0


def test_synthesis_engine_returns_no_answer_without_matches() -> None:
    result = SynthesisEngineV0().synthesize(query_profile={}, matched_chunks=[], matched_claims=[])

    assert result["answer_mode"] == "no_answer"
    assert result["answer_text"]


def test_synthesis_engine_requires_matched_chunk_before_answering() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "support service", "intent": "relation"},
        matched_chunks=[],
        matched_claims=[
            {
                "entity_name": "support service",
                "claim_id": "c-freshdesk",
                "predicate": "uses",
                "object": "Freshdesk",
                "fact_bucket": "relations",
            }
        ],
    )

    assert result["answer_mode"] == "no_answer"


def test_synthesis_engine_does_not_direct_answer_without_claim_evidence() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "support service", "intent": "relation"},
        matched_chunks=[{"entity_name": "support service"}],
        matched_claims=[
            {
                "entity_name": "support service",
                "predicate": "uses",
                "object": "Freshdesk",
                "fact_bucket": "relations",
            }
        ],
    )

    assert result["answer_mode"] == "no_answer"
    assert result["cited_claim_ids"] == []
    assert result["synthesis_debug"]["evidence_guard"].startswith("missing_")


def test_synthesis_engine_does_not_answer_for_different_explicit_entity() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "admin user", "intent": "state"},
        matched_chunks=[{"entity_name": "billing service", "conflict_marker": False}],
        matched_claims=[
            {
                "entity_name": "billing service",
                "claim_id": "c-billing-active",
                "claim_text": "currently active",
                "state": "active",
                "time_filter": "current",
            }
        ],
    )

    assert result["answer_mode"] == "no_answer"
    assert "billing service" not in result["answer_text"].lower()
    assert result["synthesis_debug"]["entity_guard"] == "explicit_entity_mismatch"


def test_synthesis_engine_filters_mixed_matches_to_explicit_entity() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "admin user", "intent": "rule"},
        matched_chunks=[
            {"entity_name": "billing service"},
            {"entity_name": "admin user"},
        ],
        matched_claims=[
            {
                "entity_name": "billing service",
                "claim_id": "c-billing",
                "predicate": "active",
                "object": "true",
                "state": "active",
                "time_filter": "current",
            },
            {
                "entity_name": "admin user",
                "claim_id": "c-admin-rule",
                "predicate": "must",
                "object": "enable two-factor authentication",
                "fact_bucket": "rules",
                "claim_group": "rule",
                "sentence_ids": ["s-admin-rule"],
                "source_ids": ["src-admin"],
            },
        ],
    )

    assert result["answer_mode"] == "direct"
    assert result["answer_text"] == "The admin user must enable two-factor authentication."
    assert result["cited_claim_ids"] == ["c-admin-rule"]


def test_synthesis_engine_unknown_intent_uses_fallback_summary_router() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "support service", "intent": "unknown"},
        matched_chunks=[{"entity_name": "support service"}],
        matched_claims=[
            {
                "entity_name": "support service",
                "claim_id": "c-freshdesk",
                "predicate": "uses",
                "object": "Freshdesk",
                "fact_bucket": "relations",
                "sentence_ids": ["s-freshdesk"],
                "source_ids": ["src-support"],
            }
        ],
    )

    assert result["answer_mode"] == "summary"
    assert result["answer_text"] == "The support service uses Freshdesk."


def test_synthesis_engine_answers_relation_query_directly() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "support service", "intent": "relation", "relation_predicate": "uses"},
        matched_chunks=[{"entity_name": "support service", "conflict_marker": False, "evidence_ids": ["e-freshdesk"]}],
        matched_claims=[
            {
                "entity_name": "support service",
                "claim_id": "c-freshdesk",
                "claim_text": "support service uses Freshdesk for customer tickets",
                "predicate": "uses",
                "object": "Freshdesk for customer tickets",
                "fact_bucket": "relations",
                "conflict_marker": False,
                "sentence_ids": ["s-freshdesk"],
                "source_ids": ["src-support"],
            }
        ],
    )

    assert result["answer_text"] == "The support service uses Freshdesk for customer tickets."
    assert result["answer_mode"] == "direct"
    assert result["cited_claim_ids"] == ["c-freshdesk"]


def test_synthesis_engine_returns_sentence_and_source_citations() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "support service", "intent": "relation"},
        matched_chunks=[
            {
                "entity_name": "support service",
                "evidence_ids": ["c-freshdesk", "s-freshdesk"],
                "source_ids": ["src-support"],
            }
        ],
        matched_claims=[
            {
                "entity_name": "support service",
                "claim_id": "c-freshdesk",
                "predicate": "uses",
                "object": "Freshdesk",
                "fact_bucket": "relations",
                "sentence_ids": ["s-freshdesk"],
                "source_ids": ["src-support"],
            }
        ],
    )

    assert result["answer_text"] == "The support service uses Freshdesk."
    assert result["cited_claim_ids"] == ["c-freshdesk"]
    assert result["cited_evidence_ids"] == ["c-freshdesk", "s-freshdesk"]
    assert result["cited_sentence_ids"] == ["s-freshdesk"]
    assert result["source_ids"] == ["src-support"]
    assert result["synthesis_debug"]["evidence"] == [
        {"claim_id": "c-freshdesk", "sentence_id": "s-freshdesk", "source_id": "src-support"}
    ]


def test_synthesis_engine_answers_rule_event_and_descriptor_queries() -> None:
    rule = SynthesisEngineV0().synthesize(
        query_profile={"entity": "admin user", "intent": "rule"},
        matched_chunks=[{"entity_name": "admin user"}],
        matched_claims=[
            {
                "entity_name": "admin user",
                "claim_id": "c-rule",
                "predicate": "must",
                "object": "enable two-factor authentication",
                "fact_bucket": "rules",
                "sentence_ids": ["s-rule"],
                "source_ids": ["src-rule"],
            }
        ],
    )
    event = SynthesisEngineV0().synthesize(
        query_profile={"entity": "billing service", "intent": "event"},
        matched_chunks=[{"entity_name": "billing service"}],
        matched_claims=[
            {
                "entity_name": "billing service",
                "claim_id": "c-event",
                "predicate": "was updated",
                "object": "in 2025",
                "fact_bucket": "events",
                "sentence_ids": ["s-event"],
                "source_ids": ["src-event"],
            }
        ],
    )
    descriptor = SynthesisEngineV0().synthesize(
        query_profile={"entity": "Sarah Miller", "intent": "descriptor"},
        matched_chunks=[{"entity_name": "Sarah Miller"}],
        matched_claims=[
            {
                "entity_name": "Sarah Miller",
                "claim_id": "c-descriptor",
                "predicate": "is the compliance lead at",
                "object": "Acme Corp",
                "fact_bucket": "descriptors",
                "sentence_ids": ["s-descriptor"],
                "source_ids": ["src-descriptor"],
            }
        ],
    )

    assert rule["answer_text"] == "The admin user must enable two-factor authentication."
    assert rule["answer_mode"] == "direct"
    assert event["answer_text"] == "The billing service was updated in 2025."
    assert event["answer_mode"] == "direct"
    assert descriptor["answer_text"] == "Sarah Miller is the compliance lead at Acme Corp."
    assert descriptor["answer_mode"] == "direct"


def test_synthesis_engine_canonicalizes_multilingual_two_factor_rule_answer() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "admin user", "intent": "rule"},
        matched_chunks=[{"entity_name": "admin user"}],
        matched_claims=[
            {
                "entity_name": "admin user",
                "claim_id": "c-rule-hu",
                "claim_text": "admin user kötelező kétfaktoros azonosítást használnia",
                "predicate": "kötelező",
                "object": "kétfaktoros azonosítást használnia",
                "fact_bucket": "rules",
                "claim_group": "rule",
                "sentence_ids": ["s-rule-hu"],
                "source_ids": ["src-rule"],
            }
        ],
    )

    assert result["answer_text"] == "The admin user must enable two-factor authentication."
    assert result["answer_mode"] == "direct"


def test_synthesis_engine_rule_fact_uses_direct_template_not_related_fallback() -> None:
    result = SynthesisEngineV0().synthesize(
        query_profile={"entity": "admin user", "intent": "rule", "rule_action": "enable"},
        matched_chunks=[{"entity_name": "admin user", "evidence_ids": ["e-rule"]}],
        matched_claims=[
            {
                "entity_name": "admin user",
                "claim_id": "c-rule",
                "claim_text": "admin user should enable recovery codes",
                "predicate": "should",
                "object": "enable recovery codes",
                "fact_bucket": "rules",
                "claim_group": "rule",
                "sentence_ids": ["s-rule"],
                "source_ids": ["src-rule"],
            }
        ],
    )

    assert result["answer_text"] == "The admin user must enable recovery codes."
    assert result["answer_mode"] == "direct"
    assert "I found related information" not in result["answer_text"]
