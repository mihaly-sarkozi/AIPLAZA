from __future__ import annotations

import pytest

from apps.knowledge.service.query_aware_retrieval_v0 import QueryAwareRetrievalV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profiles() -> list[dict[str, object]]:
    return [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [
                {"claim_id": "c-active", "subject": "London office", "predicate": "active", "object": "true", "status": "active"},
                {"claim_id": "c-inactive", "subject": "London office", "predicate": "active", "object": "false", "status": "active"},
                {
                    "claim_id": "c-2024",
                    "subject": "London office",
                    "predicate": "active",
                    "object": "false",
                    "status": "historical",
                    "time_values": ["2024"],
                },
            ],
        },
        {
            "profile_id": "global-profile:billing-service",
            "entity_name": "billing service",
            "entity_type": "system_component",
            "canonical_key": "billing service",
            "claims": [],
        },
    ]


def _chunks() -> list[dict[str, object]]:
    return [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "canonical_key": "london office",
            "retrieval_chunk_text": "\n".join(
                [
                    "London office (location)",
                    "Current facts: London office active = true; London office active = false",
                    "Conflicting current facts: London office active = true; London office active = false",
                    "Historical context: London office active = false",
                ]
            ),
            "structured_facts": {
                "active": [
                    {"claim_id": "c-active", "subject": "London office", "predicate": "active", "object": "true", "status": "active"},
                    {"claim_id": "c-inactive", "subject": "London office", "predicate": "active", "object": "false", "status": "active"},
                ],
                "conflicts": [
                    {"claim_id": "c-active", "subject": "London office", "predicate": "active", "object": "true", "status": "active"},
                    {"claim_id": "c-inactive", "subject": "London office", "predicate": "active", "object": "false", "status": "active"},
                ],
                "historical": [
                    {
                        "claim_id": "c-2024",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "historical",
                    }
                ],
            },
            "conflicting": True,
            "temporal_context_included": True,
        },
        {
            "profile_id": "global-profile:billing-service",
            "entity_name": "billing service",
            "canonical_key": "billing service",
            "retrieval_chunk_text": "billing service (system_component)\nCurrent facts: billing service uses = Stripe",
            "structured_facts": {"active": []},
            "conflicting": False,
        },
    ]


def test_query_aware_retrieval_filters_by_entity_type_and_prefers_active_state() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "location",
            "intent": "state",
            "state": "active",
            "time_filter": "current",
            "keywords": ["offices", "active"],
        },
        retrieval_chunks=_chunks(),
        global_profiles=_profiles(),
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["query_retrieval_filtered_count"] == 1
    assert result["filtered_out_reason"][0]["reason"] == "entity_type_mismatch"
    assert result["conflict_marker_included"] is True
    assert any(item["claim_id"] == "c-active" for item in result["matched_claims"])
    assert any(item["claim_id"] == "c-inactive" for item in result["matched_claims"])


def test_query_aware_retrieval_historical_question_prioritizes_historical_claim() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "location",
            "entity": "London office",
            "intent": "state",
            "state": "inactive",
            "time_filter": "historical",
            "keywords": ["london", "office", "inactive"],
        },
        retrieval_chunks=_chunks(),
        global_profiles=_profiles(),
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["temporal_context_used"] is True
    assert result["matched_claims"][0]["claim_id"] == "c-2024"
    assert result["matched_claims"][0]["time_filter"] == "historical"


def test_query_aware_retrieval_status_question_keeps_current_conflict_and_historical() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "location",
            "entity": "London office",
            "intent": "state",
            "time_filter": None,
            "keywords": ["status", "london", "office"],
        },
        retrieval_chunks=_chunks(),
        global_profiles=_profiles(),
    )

    claim_ids = [item["claim_id"] for item in result["matched_claims"]]
    assert {"c-active", "c-inactive", "c-2024"}.issubset(set(claim_ids))
    assert result["conflict_marker_included"] is True
    assert result["temporal_context_used"] is True


def test_query_aware_retrieval_matches_system_component_query_to_software_profile_by_entity_keywords() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "system_component",
            "entity": None,
            "intent": "relation",
            "keywords": ["support", "service", "use", "relation"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "retrieval_chunk_text": "support service (software)",
                "structured_facts": {},
                "conflicting": False,
            }
        ],
        global_profiles=[
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "claims": [
                    {
                        "claim_id": "c-freshdesk",
                        "subject": "support service",
                        "predicate": "uses",
                        "object": "Freshdesk for customer tickets",
                        "status": "active",
                    }
                ],
            }
        ],
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_chunks"][0]["entity_name"] == "support service"
    assert result["matched_claims"][0]["claim_id"] == "c-freshdesk"


def test_query_aware_retrieval_relation_query_uses_explicit_entity_profile_only() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "system_component",
            "entity": "support service",
            "intent": "relation",
            "relation_predicate": "uses",
            "keywords": ["support", "service", "use"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "retrieval_chunk_text": "support service (software)\nRelation facts:\n- uses Freshdesk for customer tickets",
                "structured_facts": {
                    "relations": [
                        {
                            "claim_id": "c-freshdesk",
                            "subject": "support service",
                            "predicate": "uses",
                            "object": "Freshdesk for customer tickets",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            },
            {
                "profile_id": "global-profile:billing-service",
                "entity_name": "billing service",
                "entity_type": "software",
                "canonical_key": "billing service",
                "retrieval_chunk_text": "billing service (software)\nRelation facts:\n- uses support service metrics",
                "structured_facts": {
                    "relations": [
                        {
                            "claim_id": "c-billing",
                            "subject": "billing service",
                            "predicate": "uses",
                            "object": "support service metrics",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            },
        ],
        global_profiles=[
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "claims": [],
            },
            {
                "profile_id": "global-profile:billing-service",
                "entity_name": "billing service",
                "entity_type": "software",
                "canonical_key": "billing service",
                "claims": [],
            },
        ],
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_chunks"][0]["profile_id"] == "global-profile:support-service"
    assert result["matched_claims"][0]["claim_text"] == "support service uses Freshdesk for customer tickets"


def test_query_aware_retrieval_rejects_location_question_without_location_claim() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "location",
            "entity": "London office",
            "intent": "state",
            "expected_answer_type": "location",
            "keywords": ["hol", "london", "office"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "retrieval_chunk_text": "London office (location)\nCurrent facts:\n- currently inactive",
                "structured_facts": {
                    "active": [
                        {
                            "claim_id": "c-inactive",
                            "subject": "London office",
                            "predicate": "active",
                            "object": "false",
                            "status": "active",
                        }
                    ]
                },
            }
        ],
        global_profiles=[
            {
                "profile_id": "global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "claims": [],
            }
        ],
    )

    assert result["query_retrieval_match_count"] == 0
    assert result["filtered_out_reason"][0]["reason"] == "semantic_answer_type_mismatch"
    assert result["filtered_out_reason"][0]["expected_answer_type"] == "location"


def test_query_aware_retrieval_keeps_location_question_with_location_claim() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "location",
            "entity": "London office",
            "intent": "descriptor",
            "expected_answer_type": "location",
            "keywords": ["hol", "london", "office"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "retrieval_chunk_text": "London office (location)\nDescriptors:\n- located in Budapest",
                "structured_facts": {
                    "descriptors": [
                        {
                            "claim_id": "c-location",
                            "subject": "London office",
                            "predicate": "located_in",
                            "object": "Budapest",
                            "status": "active",
                            "claim_group": "descriptor",
                        }
                    ]
                },
            }
        ],
        global_profiles=[
            {
                "profile_id": "global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "claims": [],
            }
        ],
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_claims"][0]["claim_id"] == "c-location"
    assert result["matched_claims"][0]["claim_semantic_type"] == "descriptor"


def test_query_aware_retrieval_rule_query_matches_only_explicit_canonical_rule_profile() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "user",
            "entity": "admin user",
            "intent": "rule",
            "rule_action": "enable",
            "keywords": ["admin", "user", "enable", "rule"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:admin-user",
                "entity_name": "admin user",
                "entity_type": "user",
                "canonical_key": "admin user",
                "retrieval_chunk_text": "admin user (user)\nRules:\n- must enable two-factor authentication",
                "structured_facts": {
                    "rules": [
                        {
                            "claim_id": "c-rule",
                            "subject": "admin user",
                            "predicate": "must",
                            "object": "enable two-factor authentication",
                            "claim_group": "rule",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            },
            {
                "profile_id": "global-profile:billing-service",
                "entity_name": "billing service",
                "entity_type": "software",
                "canonical_key": "billing service",
                "retrieval_chunk_text": "billing service mentions admin user but has no admin user canonical key",
                "structured_facts": {
                    "rules": [
                        {
                            "claim_id": "c-billing-rule",
                            "subject": "billing service",
                            "predicate": "must",
                            "object": "notify admin user",
                            "claim_group": "rule",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            },
            {
                "profile_id": "global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "retrieval_chunk_text": "London office (location)",
                "structured_facts": {
                    "current": [
                        {
                            "claim_id": "c-london",
                            "subject": "London office",
                            "predicate": "active",
                            "object": "true",
                            "status": "active",
                            "time_mode": "current",
                        }
                    ]
                },
                "conflicting": False,
            },
        ],
        global_profiles=[
            {"profile_id": "global-profile:admin-user", "entity_name": "admin user", "entity_type": "user", "canonical_key": "admin user", "claims": []},
            {
                "profile_id": "global-profile:billing-service",
                "entity_name": "billing service",
                "entity_type": "software",
                "canonical_key": "billing service",
                "claims": [],
            },
            {"profile_id": "global-profile:london-office", "entity_name": "London office", "entity_type": "location", "canonical_key": "london office", "claims": []},
        ],
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_chunks"][0]["profile_id"] == "global-profile:admin-user"
    assert [claim["claim_id"] for claim in result["matched_claims"]] == ["c-rule"]
    assert {item["entity_name"] for item in result["filtered_out_reason"]} == {"billing service", "London office"}


def test_query_aware_retrieval_rule_query_returns_no_match_without_rule_claim() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "user",
            "entity": "admin user",
            "intent": "rule",
            "rule_action": "enable",
            "keywords": ["admin", "user", "enable", "rule"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:admin-user",
                "entity_name": "admin user",
                "entity_type": "user",
                "canonical_key": "admin user",
                "retrieval_chunk_text": "admin user (user)\nCurrent facts:\n- currently active",
                "structured_facts": {
                    "current": [
                        {
                            "claim_id": "c-state",
                            "subject": "admin user",
                            "predicate": "active",
                            "object": "true",
                            "status": "active",
                            "time_mode": "current",
                        }
                    ]
                },
                "conflicting": False,
            }
        ],
        global_profiles=[
            {"profile_id": "global-profile:admin-user", "entity_name": "admin user", "entity_type": "user", "canonical_key": "admin user", "claims": []}
        ],
    )

    assert result["query_retrieval_match_count"] == 0
    assert result["matched_claims"] == []
    assert result["filtered_out_reason"][0]["reason"] == "rule_claim_mismatch"


def test_query_aware_retrieval_relation_object_query_matches_claim_object() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "system_component",
            "entity": None,
            "intent": "relation",
            "relation_predicate": "uses",
            "relation_object": "Freshdesk",
            "keywords": ["systems", "use", "freshdesk", "relation"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "retrieval_chunk_text": "support service (software)\nRelation facts:\n- uses Freshdesk for customer tickets",
                "structured_facts": {
                    "relations": [
                        {
                            "claim_id": "c-freshdesk",
                            "subject": "support service",
                            "predicate": "uses",
                            "object": "Freshdesk for customer tickets",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            },
            {
                "profile_id": "global-profile:billing-service",
                "entity_name": "billing service",
                "entity_type": "software",
                "canonical_key": "billing service",
                "retrieval_chunk_text": "billing service (software)\nRelation facts:\n- uses Stripe",
                "structured_facts": {
                    "relations": [
                        {
                            "claim_id": "c-stripe",
                            "subject": "billing service",
                            "predicate": "uses",
                            "object": "Stripe",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            },
        ],
        global_profiles=[
            {"profile_id": "global-profile:support-service", "entity_name": "support service", "entity_type": "software", "canonical_key": "support service", "claims": []},
            {"profile_id": "global-profile:billing-service", "entity_name": "billing service", "entity_type": "software", "canonical_key": "billing service", "claims": []},
        ],
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_chunks"][0]["entity_name"] == "support service"
    assert result["matched_claims"][0]["claim_text"] == "support service uses Freshdesk for customer tickets"


def test_query_aware_retrieval_relation_integrates_query_can_match_uses_claim() -> None:
    result = QueryAwareRetrievalV0().match(
        query_profile={
            "entity_type": "system_component",
            "entity": "support service",
            "intent": "relation",
            "relation_predicate": "integrates",
            "keywords": ["support", "service", "integrate", "relation"],
        },
        retrieval_chunks=[
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "retrieval_chunk_text": "support service (software)\nRelation facts:\n- uses Freshdesk for customer tickets",
                "structured_facts": {
                    "relations": [
                        {
                            "claim_id": "c-freshdesk",
                            "subject": "support service",
                            "predicate": "uses",
                            "object": "Freshdesk for customer tickets",
                            "status": "active",
                        }
                    ]
                },
                "conflicting": False,
            }
        ],
        global_profiles=[
            {"profile_id": "global-profile:support-service", "entity_name": "support service", "entity_type": "software", "canonical_key": "support service", "claims": []}
        ],
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_claims"][0]["claim_id"] == "c-freshdesk"
