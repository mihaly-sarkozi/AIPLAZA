from __future__ import annotations

import pytest

from apps.knowledge.service.query_aware_retrieval_v0 import QueryAwareRetrievalV0
from apps.knowledge.service.query_resolver_v0 import QueryResolverV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _chunks() -> list[dict[str, object]]:
    return [
        {
            "profile_id": "global-profile:support-service",
            "entity_name": "support service",
            "entity_type": "software",
            "canonical_key": "support service",
            "retrieval_chunk_text": "support service uses Freshdesk for customer tickets",
            "structured_facts": {
                "relations": [
                    {
                        "claim_id": "c-support-freshdesk",
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
            "retrieval_chunk_text": "billing service uses Stripe for payments",
            "structured_facts": {
                "relations": [
                    {
                        "claim_id": "c-billing-stripe",
                        "subject": "billing service",
                        "predicate": "uses",
                        "object": "Stripe for payments",
                        "status": "active",
                    }
                ]
            },
            "conflicting": False,
        },
    ]


def _profiles() -> list[dict[str, object]]:
    return [
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
    ]


@pytest.mark.parametrize(
    ("query", "profile_override"),
    [
        ("What does the support service use?", None),
        ("Which system does the support service use?", None),
        (
            "Milyen rendszert hasznal a support service?",
            {
                "entity_type": "system_component",
                "entity": "support service",
                "intent": "relation",
                "relation_predicate": "uses",
                "keywords": ["support", "service", "hasznal"],
            },
        ),
        (
            "Que usa el support service?",
            {
                "entity_type": "system_component",
                "entity": "support service",
                "intent": "relation",
                "relation_predicate": "uses",
                "keywords": ["support", "service", "usa"],
            },
        ),
    ],
)
def test_relation_paraphrase_matrix_keeps_same_top_profile(query: str, profile_override: dict[str, object] | None) -> None:
    profile = QueryResolverV0().resolve(query)
    query_profile = profile_override or {
        "entity_type": profile.entity_type,
        "entity": profile.entity,
        "intent": profile.intent,
        "relation_predicate": profile.relation_predicate,
        "keywords": profile.keywords,
    }
    result = QueryAwareRetrievalV0().match(
        query_profile=query_profile,
        retrieval_chunks=_chunks(),
        global_profiles=_profiles(),
    )

    assert result["query_retrieval_match_count"] == 1
    assert result["matched_chunks"][0]["profile_id"] == "global-profile:support-service"
    assert result["matched_claims"][0]["claim_id"] == "c-support-freshdesk"
