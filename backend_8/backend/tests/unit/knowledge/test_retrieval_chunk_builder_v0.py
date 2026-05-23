from __future__ import annotations

import pytest

from apps.knowledge.service.retrieval_chunk_builder_v0 import RetrievalChunkBuilderV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profile(claims):
    return {
        "profile_id": "global-profile:london-office",
        "entity_name": "London office",
        "entity_type": "location",
        "canonical_key": "london office",
        "decision_confidence": 0.85,
        "claims": claims,
    }


def test_retrieval_chunk_builder_uses_active_claims_only_by_default() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            _profile(
                [
                    {"claim_id": "c-active", "subject": "London office", "predicate": "active", "object": "true", "status": "active", "time_mode": "current"},
                    {
                        "claim_id": "c-old",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "historical",
                    },
                ]
            )
        ],
        [],
    )

    assert len(chunks) == 1
    assert "Current facts:\n- currently active" in chunks[0]["retrieval_chunk_text"]
    assert "Historical facts:\n- inactive" in chunks[0]["retrieval_chunk_text"]
    assert chunks[0]["structured_facts"]["current"]
    assert chunks[0]["structured_facts"]["historical"]
    assert chunks[0]["structured_facts"]["current"] != chunks[0]["structured_facts"]["historical"]


def test_retrieval_chunk_builder_includes_both_sides_for_hard_conflict() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            _profile(
                [
                    {"claim_id": "c-active", "subject": "London office", "predicate": "active", "object": "true", "status": "active", "time_mode": "current"},
                    {"claim_id": "c-inactive", "subject": "London office", "predicate": "active", "object": "false", "status": "active", "time_mode": "current"},
                ]
            )
        ],
        [
            {
                "tension_detected": True,
                "tension_type": "hard_conflict",
                "conflicting_claim_ids": ["c-active", "c-inactive"],
                "evidence": {"profile_id": "global-profile:london-office"},
            }
        ],
    )

    chunk = chunks[0]
    assert chunk["conflicting"] is True
    assert "Conflicts:" in chunk["retrieval_chunk_text"]
    assert "- currently active" in chunk["retrieval_chunk_text"]
    assert "- currently inactive" in chunk["retrieval_chunk_text"]
    assert chunk["confidence"] <= 0.65


def test_retrieval_chunk_builder_includes_historical_context_for_temporal_change() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            _profile(
                [
                    {"claim_id": "c-current", "subject": "London office", "predicate": "active", "object": "true", "status": "active", "time_mode": "current"},
                    {
                        "claim_id": "c-2024",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "historical",
                        "time_values": ["2024"],
                    },
                ]
            )
        ],
        [
            {
                "tension_detected": True,
                "tension_type": "temporal_change",
                "conflicting_claim_ids": ["c-current", "c-2024"],
                "evidence": {"profile_id": "global-profile:london-office"},
            }
        ],
    )

    chunk = chunks[0]
    assert chunk["temporal_context_included"] is True
    assert "Current facts:\n- currently active" in chunk["retrieval_chunk_text"]
    assert "Historical facts:\n- inactive in 2024" in chunk["retrieval_chunk_text"]
    assert chunk["structured_facts"]["historical"]


def test_retrieval_chunk_builder_materializes_location_state_claims_without_predicate_object() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            _profile(
                [
                    {
                        "claim_id": "c-current",
                        "subject": "London office",
                        "predicate_text": "is currently inactive",
                        "object_text": None,
                        "claim_text": "",
                        "status": "active",
                        "time_dominant": "current",
                    },
                    {
                        "claim_id": "c-2024",
                        "subject": "London office",
                        "predicate_text": "was inactive",
                        "object_text": "in 2024",
                        "status": "historical",
                        "time_dominant": "historical",
                        "time_values": ["2024"],
                    },
                ]
            )
        ],
        [],
    )

    text = chunks[0]["retrieval_chunk_text"]
    assert "London office (location)" in text
    assert "Current facts:\n- currently inactive" in text
    assert "Historical facts:\n- inactive in 2024" in text
    assert "Historical facts:\n- currently inactive" not in text


def test_retrieval_chunk_builder_deduplicates_state_claims_by_subject_predicate_object() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            _profile(
                [
                    {
                        "claim_id": "c-current-1",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "active",
                        "time_mode": "current",
                    },
                    {
                        "claim_id": "c-current-2",
                        "subject": "London office",
                        "predicate_text": "is currently inactive",
                        "object_text": None,
                        "status": "active",
                        "time_mode": "current",
                    },
                    {
                        "claim_id": "c-2024-1",
                        "subject": "London office",
                        "predicate_text": "was inactive",
                        "object_text": "in 2024",
                        "status": "historical",
                        "time_mode": "bounded",
                        "time_values": ["2024"],
                    },
                    {
                        "claim_id": "c-2024-2",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "historical",
                        "time_mode": "bounded",
                        "time_values": ["2024"],
                    },
                ]
            )
        ],
        [],
    )

    text = chunks[0]["retrieval_chunk_text"]
    assert text.count("- currently inactive") == 1
    assert text.count("- inactive in 2024") == 1
    assert chunks[0]["structured_facts"]["current"] != chunks[0]["structured_facts"]["historical"]


def test_retrieval_chunk_builder_separates_current_and_bounded_location_state_claims() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            _profile(
                [
                    {
                        "claim_id": "c-active",
                        "subject": "London office",
                        "predicate_text": "is currently active",
                        "claim_text": "London office inactive in 2024, currently",
                        "time_mode": "current",
                    },
                    {
                        "claim_id": "c-inactive",
                        "subject": "London office",
                        "predicate_text": "is currently inactive",
                        "claim_text": "London office inactive in 2024, currently",
                        "time_mode": "current",
                    },
                    {
                        "claim_id": "c-2024",
                        "subject": "London office",
                        "predicate_text": "was inactive",
                        "claim_text": "London office inactive in 2024, currently",
                        "time_mode": "bounded",
                        "time_values": ["2024"],
                    },
                ]
            )
        ],
        [
            {
                "tension_detected": True,
                "tension_type": "contradiction",
                "conflicting_claim_ids": ["c-active", "c-inactive"],
                "evidence": {"profile_id": "global-profile:london-office"},
            }
        ],
    )

    chunk = chunks[0]
    text = chunk["retrieval_chunk_text"]
    assert "London office (location)" in text
    assert "Current facts:\n- currently active\n- currently inactive" in text
    assert "Historical facts:\n- inactive in 2024" in text
    assert "Current facts:\n- inactive in 2024, currently" not in text
    assert "Historical facts:\n- inactive in 2024, currently" not in text
    assert chunk["conflicting"] is True
    assert chunk["temporal_context_included"] is True


def test_retrieval_chunk_builder_includes_rule_obligation_facts() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            {
                "profile_id": "global-profile:admin-user",
                "entity_name": "admin user",
                "entity_type": "user",
                "canonical_key": "admin user",
                "decision_confidence": 0.85,
                "claims": [
                    {
                        "claim_id": "c-rule",
                        "subject": "admin user",
                        "predicate": "must",
                        "object": "enable two-factor authentication",
                        "claim_type": "rule_procedure",
                        "claim_group": "rule",
                        "status": "active",
                        "time_mode": "timeless",
                    }
                ],
            }
        ],
        [],
    )

    chunk = chunks[0]
    assert "Current facts:" not in chunk["retrieval_chunk_text"]
    assert "Historical facts:" not in chunk["retrieval_chunk_text"]
    assert "Relation facts:" not in chunk["retrieval_chunk_text"]
    assert "Rules:\n- must enable two-factor authentication" in chunk["retrieval_chunk_text"]
    assert "Descriptors:" not in chunk["retrieval_chunk_text"]
    assert "Events:" not in chunk["retrieval_chunk_text"]
    assert "Conflicts:" not in chunk["retrieval_chunk_text"]
    assert chunk["structured_facts"]["rules"][0]["claim_id"] == "c-rule"


def test_retrieval_chunk_builder_canonicalizes_multilingual_rule_obligations() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            {
                "profile_id": "global-profile:admin-user",
                "entity_name": "admin user",
                "entity_type": "user",
                "canonical_key": "admin user",
                "decision_confidence": 0.85,
                "claims": [
                    {
                        "claim_id": "c-hu",
                        "subject": "admin user",
                        "predicate": "kötelező",
                        "object": "kétfaktoros azonosítást használnia",
                        "claim_type": "rule_procedure",
                        "claim_group": "rule",
                        "status": "active",
                        "time_mode": "timeless",
                    },
                    {
                        "claim_id": "c-en",
                        "subject": "admin user",
                        "predicate": "must",
                        "object": "enable two-factor authentication",
                        "claim_type": "rule_procedure",
                        "claim_group": "rule",
                        "status": "active",
                        "time_mode": "timeless",
                    },
                    {
                        "claim_id": "c-es",
                        "subject": "admin user",
                        "predicate": "debe",
                        "object": "activar la autenticación de dos factores",
                        "claim_type": "rule_procedure",
                        "claim_group": "rule",
                        "status": "active",
                        "time_mode": "timeless",
                    },
                ],
            }
        ],
        [],
    )

    chunk = chunks[0]
    assert "Rules:\n- must enable two-factor authentication" in chunk["retrieval_chunk_text"]
    assert len(chunk["structured_facts"]["rules"]) == 1
    assert "activar la autenticación" not in chunk["retrieval_chunk_text"]
    assert "kétfaktoros azonosítást" not in chunk["retrieval_chunk_text"]


def test_retrieval_chunk_builder_includes_relation_facts() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            {
                "profile_id": "global-profile:support-service",
                "entity_name": "support service",
                "entity_type": "software",
                "canonical_key": "support service",
                "decision_confidence": 0.85,
                "claims": [
                    {
                        "claim_id": "c-freshdesk",
                        "subject": "support service",
                        "predicate": "uses",
                        "object": "Freshdesk for customer tickets",
                        "status": "active",
                        "time_mode": "timeless",
                    }
                ],
            }
        ],
        [],
    )

    chunk = chunks[0]
    assert "Relation facts:\n- uses Freshdesk for customer tickets" in chunk["retrieval_chunk_text"]
    assert chunk["structured_facts"]["relations"][0]["claim_id"] == "c-freshdesk"
    assert "c-freshdesk" in chunk["evidence_ids"]


def test_retrieval_chunk_builder_routes_all_active_claim_types_and_excludes_revoked() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            {
                "profile_id": "global-profile:security-policy",
                "entity_name": "security policy",
                "entity_type": "policy",
                "canonical_key": "security policy",
                "decision_confidence": 0.85,
                "claims": [
                    {
                        "claim_id": "c-state",
                        "subject": "security policy",
                        "predicate": "active",
                        "object": "true",
                        "status": "active",
                        "time_mode": "current",
                    },
                    {
                        "claim_id": "c-relation",
                        "subject": "security policy",
                        "predicate": "uses",
                        "object": "risk matrix",
                        "claim_group": "relation",
                        "status": "active",
                    },
                    {
                        "claim_id": "c-rule",
                        "subject": "security policy",
                        "predicate": "must",
                        "object": "enable review approval",
                        "claim_group": "rule",
                        "status": "active",
                    },
                    {
                        "claim_id": "c-descriptor",
                        "subject": "security policy",
                        "predicate": "applies to",
                        "object": "all contractors",
                        "claim_group": "descriptor",
                        "status": "active",
                    },
                    {
                        "claim_id": "c-event",
                        "subject": "security policy",
                        "predicate": "was completed",
                        "object": "on 12 March 2025",
                        "claim_group": "event",
                        "status": "historical",
                        "time_mode": "event",
                    },
                    {
                        "claim_id": "c-old-relation",
                        "subject": "security policy",
                        "predicate": "uses",
                        "object": "legacy checklist",
                        "claim_group": "relation",
                        "status": "historical",
                    },
                    {
                        "claim_id": "c-revoked-rule",
                        "subject": "security policy",
                        "predicate": "must",
                        "object": "use revoked process",
                        "claim_group": "rule",
                        "claim_status": "revoked",
                    },
                    {
                        "claim_id": "c-banned-descriptor",
                        "subject": "security policy",
                        "predicate": "contains",
                        "object": "banned note",
                        "claim_group": "descriptor",
                        "status": "banned",
                    },
                ],
            }
        ],
        [],
    )

    text = chunks[0]["retrieval_chunk_text"]
    assert "Current facts:\n- currently active" in text
    assert "Historical facts:\n- security policy uses legacy checklist" in text
    assert "Relation facts:\n- uses risk matrix" in text
    assert "Rules:\n- must enable review approval" in text
    assert "Descriptors:\n- applies to all contractors" in text
    assert "Events:\n- completed on 12 March 2025" in text
    assert "revoked process" not in text
    assert "banned note" not in text
    assert [claim["claim_id"] for claim in chunks[0]["structured_facts"]["relations"]] == ["c-relation"]
    assert [claim["claim_id"] for claim in chunks[0]["structured_facts"]["rules"]] == ["c-rule"]
    assert [claim["claim_id"] for claim in chunks[0]["structured_facts"]["descriptors"]] == ["c-descriptor"]
    assert [claim["claim_id"] for claim in chunks[0]["structured_facts"]["historical"]] == ["c-old-relation"]


def test_retrieval_chunk_builder_includes_descriptor_and_event_facts() -> None:
    chunks = RetrievalChunkBuilderV0().build_many(
        [
            {
                "profile_id": "global-profile:sarah-miller",
                "entity_name": "Sarah Miller",
                "entity_type": "person",
                "canonical_key": "miller sarah",
                "decision_confidence": 0.85,
                "claims": [
                    {
                        "claim_id": "c-descriptor",
                        "subject": "Sarah Miller",
                        "predicate": "is the compliance lead at",
                        "object": "Acme Corp",
                        "claim_type": "stable_descriptor",
                        "claim_group": "descriptor",
                        "status": "active",
                    }
                ],
            },
            {
                "profile_id": "global-profile:billing-service",
                "entity_name": "billing service",
                "entity_type": "software",
                "canonical_key": "billing service",
                "decision_confidence": 0.85,
                "claims": [
                    {
                        "claim_id": "c-event",
                        "subject": "billing service",
                        "claim_text": "billing service was updated in 2025",
                        "predicate": "was updated",
                        "object": "in 2025",
                        "claim_type": "event",
                        "claim_group": "event",
                        "status": "historical",
                        "time_mode": "event",
                        "time_values": ["2025"],
                    }
                ],
            },
        ],
        [],
    )

    assert "Descriptors:\n- is the compliance lead at Acme Corp" in chunks[0]["retrieval_chunk_text"]
    assert chunks[0]["structured_facts"]["descriptors"][0]["claim_id"] == "c-descriptor"
    assert "Events:\n- updated in 2025" in chunks[1]["retrieval_chunk_text"]
    assert chunks[1]["structured_facts"]["events"][0]["claim_id"] == "c-event"
