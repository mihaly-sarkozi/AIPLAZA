from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.decision_analysis import DecisionAnalysis
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.global_profile_builder_v0 import GlobalProfileBuilderV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profile(name: str, *, claim_id: str = "c1") -> SearchProfile:
    return SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name=name,
        entity_type="module",
        normalized_key=name.lower(),
        canonical_key=name.lower(),
        evidence_refs=[{"claim_ids": [claim_id], "sentence_ids": [f"s-{claim_id}"]}],
    )


def test_global_profile_builder_updates_existing_and_creates_new_profiles() -> None:
    existing_candidate = _profile("support module", claim_id="old-c")
    profile_attach = _profile("support module", claim_id="new-c")
    profile_create = _profile("new workflow", claim_id="create-c")
    decisions = [
        DecisionAnalysis(
            search_profile_id=profile_attach.search_profile_id,
            technical_entity_id=profile_attach.technical_entity_id,
            decision="attach_existing",
            decision_type="attach_existing",
            selected_candidate_id=str(existing_candidate.technical_entity_id),
            decision_confidence=0.85,
            decision_reason="attach_existing:single_high_similarity_candidate",
            evidence={"claim_ids": ["new-c"], "sentence_ids": ["s-new-c"]},
        ),
        DecisionAnalysis(
            search_profile_id=profile_create.search_profile_id,
            technical_entity_id=profile_create.technical_entity_id,
            decision="create_new_profile",
            decision_type="create_new_profile",
            decision_confidence=0.75,
            decision_reason="create_new_profile:no_candidate_above_threshold",
            evidence={"claim_ids": ["create-c"], "sentence_ids": ["s-create-c"]},
        ),
    ]

    rows = GlobalProfileBuilderV0().build_many(
        decisions,
        [profile_attach, profile_create],
        candidate_profiles=[existing_candidate],
        existing_global_profiles=[
            {
                "profile_id": "global-profile:support-module",
                "canonical_key": "support module",
                "entity_name": "support module",
                "entity_type": "module",
                "claims": [{"claim_id": "old-c", "status": "active"}],
                "evidence": {"claim_ids": ["old-c"], "sentence_ids": ["s-old-c"]},
            }
        ],
    )

    assert [row["operation"] for row in rows] == ["update", "create"]
    assert rows[0]["profile_id"] == "global-profile:support-module"
    assert rows[0]["claim_added_count"] == 1
    assert rows[0]["claim_deduplicated_count"] == 0
    assert {claim["claim_id"] for claim in rows[0]["claims"]} == {"old-c", "new-c"}
    assert rows[1]["created_profile_id"].startswith("global-profile:")
    assert rows[1]["claim_added_count"] == 1
    assert rows[0]["decision_confidence"] == 0.85
    assert rows[0]["builder_version"] == "global_profile_builder_v0"


def test_global_profile_builder_deduplicates_existing_claims_and_marks_review() -> None:
    existing_candidate = _profile("support module", claim_id="same-c")
    new_profile = _profile("support module", claim_id="same-c")
    uncertain = _profile("possible match", claim_id="review-c")
    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=new_profile.search_profile_id,
                technical_entity_id=new_profile.technical_entity_id,
                decision="attach_existing",
                decision_type="attach_existing",
                selected_candidate_id=str(existing_candidate.technical_entity_id),
                evidence={"claim_ids": ["same-c"], "sentence_ids": ["s-same-c"]},
            ),
            DecisionAnalysis(
                search_profile_id=uncertain.search_profile_id,
                technical_entity_id=uncertain.technical_entity_id,
                decision="uncertain_match",
                decision_type="uncertain_match",
                selected_candidate_id=str(existing_candidate.technical_entity_id),
                evidence={"claim_ids": ["review-c"], "sentence_ids": ["s-review-c"]},
            ),
        ],
        [new_profile, uncertain],
        candidate_profiles=[existing_candidate],
        existing_global_profiles=[
            {
                "profile_id": "global-profile:support-module",
                "canonical_key": "support module",
                "claims": [{"claim_id": "same-c", "status": "active"}],
            }
        ],
    )

    assert rows[0]["operation"] == "update"
    assert rows[0]["claim_added_count"] == 0
    assert rows[0]["claim_deduplicated_count"] == 1
    assert rows[1]["operation"] == "review"
    assert rows[1]["manual_review_required"] is True


def test_global_profile_builder_splits_profile_with_multiple_entity_claim_subjects() -> None:
    existing_candidate = _profile("support service", claim_id="existing-support")
    incoming = _profile("support service", claim_id="incoming-support")

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=incoming.search_profile_id,
                technical_entity_id=incoming.technical_entity_id,
                decision="attach_existing",
                decision_type="attach_existing",
                selected_candidate_id=str(existing_candidate.technical_entity_id),
                evidence={"claim_ids": ["incoming-support"], "sentence_ids": ["s-incoming-support"]},
            )
        ],
        [incoming],
        candidate_profiles=[existing_candidate],
        existing_global_profiles=[
            {
                "profile_id": "global-profile:support-service",
                "canonical_key": "support service",
                "entity_name": "support service",
                "entity_type": "software",
                "claims": [
                    {
                        "claim_id": "support-claim",
                        "subject": "support service",
                        "predicate": "uses",
                        "object": "Freshdesk",
                        "sentence_ids": ["s-support"],
                    },
                    {
                        "claim_id": "billing-claim",
                        "subject": "billing service",
                        "predicate": "uses",
                        "object": "Stripe",
                        "sentence_ids": ["s-billing"],
                    },
                ],
                "evidence": {
                    "claim_ids": ["support-claim", "billing-claim"],
                    "sentence_ids": ["s-support", "s-billing"],
                },
            }
        ],
    )

    assert len(rows) == 2
    assert {row["canonical_key"] for row in rows} == {"support service", "billing service"}
    support = next(row for row in rows if row["canonical_key"] == "support service")
    billing = next(row for row in rows if row["canonical_key"] == "billing service")
    assert {claim["claim_id"] for claim in support["claims"]} == {"support-claim", "incoming-support"}
    assert {claim["claim_id"] for claim in billing["claims"]} == {"billing-claim"}
    assert billing["operation"] == "split_create"
    assert billing["profile_split"] is True


def test_global_profile_builder_merges_duplicate_profiles_and_deduplicates_claims() -> None:
    first = _profile("support service", claim_id="support-c-1")
    second = _profile("support service", claim_id="support-c-2")

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=first.search_profile_id,
                technical_entity_id=first.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
                evidence={"claim_ids": ["support-c-1"], "sentence_ids": ["s-support-c-1"]},
            ),
            DecisionAnalysis(
                search_profile_id=second.search_profile_id,
                technical_entity_id=second.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
                evidence={"claim_ids": ["support-c-2"], "sentence_ids": ["s-support-c-2"]},
            ),
        ],
        [first, second],
    )

    assert len(rows) == 1
    assert rows[0]["profile_merged"] is True
    assert rows[0]["claim_deduplicated_count"] == 1
    assert [claim["claim_id"] for claim in rows[0]["claims"]] == ["support-c-1"]


def test_global_profile_builder_materializes_state_claim_predicate_and_object() -> None:
    active = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="London office",
        entity_type="location",
        normalized_key="london office",
        canonical_key="london office",
        canonical_text="London office | location | is currently active",
        search_text="London office is currently active",
        keywords=["london", "office", "active"],
        time_filters={"dominant": "current", "values": ["currently"], "has_current": True},
        evidence_refs=[{"claim_ids": ["active-c"], "sentence_ids": ["s-active"]}],
    )

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=active.search_profile_id,
                technical_entity_id=active.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            )
        ],
        [active],
    )

    claim = rows[0]["claims"][0]
    assert claim["predicate"] == "active"
    assert claim["object"] == "true"
    assert claim["time_dominant"] == "current"


def test_global_profile_builder_materializes_separate_current_and_bounded_state_claims() -> None:
    profile = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="London office",
        entity_type="location",
        normalized_key="london office",
        canonical_key="london office",
        canonical_text="London office | location | inactive in 2024 | currently inactive | London office",
        search_text="London office állapotai: is currently inactive; was inactive → in 2024.",
        keywords=["london", "office", "inactive"],
        time_filters={"dominant": "current", "values": ["2024", "currently"], "has_current": True, "has_historical": True},
        evidence_refs=[{"claim_ids": ["c-current", "c-2024"], "sentence_ids": ["s-current", "s-2024"]}],
    )

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=profile.search_profile_id,
                technical_entity_id=profile.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            )
        ],
        [profile],
    )

    claims = rows[0]["claims"]
    technical_child_id = f"technical_entity:{rows[0]['profile_id']}"
    assert claims == [
        {
            "claim_id": "c-current",
            "subject": "London office",
            "predicate": "active",
            "predicate_text": "is currently inactive",
            "predicates": ["active"],
            "object": "false",
            "objects": ["false"],
            "time_dominant": "current",
            "time_mode": "current",
            "time_values": ["currently"],
            "status": "active",
            "sentence_ids": ["s-current"],
            "evidence": {"claim_ids": ["c-current", "c-2024"], "sentence_ids": ["s-current", "s-2024"]},
            "parent_ids": ["s-current"],
            "child_ids": [technical_child_id],
        },
        {
            "claim_id": "c-2024",
            "subject": "London office",
            "predicate": "active",
            "predicate_text": "was inactive",
            "predicates": ["active"],
            "object": "false",
            "objects": ["false"],
            "time_dominant": "bounded",
            "time_mode": "bounded",
            "time_values": ["2024"],
            "status": "historical",
            "sentence_ids": ["s-2024"],
            "evidence": {"claim_ids": ["c-current", "c-2024"], "sentence_ids": ["s-current", "s-2024"]},
            "parent_ids": ["s-2024"],
            "child_ids": [technical_child_id],
        },
    ]


def test_global_profile_builder_materializes_rule_obligation_claim() -> None:
    profile = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="admin user",
        entity_type="user",
        normalized_key="admin user",
        canonical_key="admin user",
        canonical_text="admin user | user | must enable two-factor authentication",
        search_text="admin user must enable two-factor authentication",
        evidence_refs=[{"claim_ids": ["c-rule"], "sentence_ids": ["s-rule"]}],
    )

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=profile.search_profile_id,
                technical_entity_id=profile.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            )
        ],
        [profile],
    )

    assert rows[0]["claims"][0]["predicate"] == "must"
    assert rows[0]["claims"][0]["object"] == "enable two-factor authentication"
    assert rows[0]["claims"][0]["claim_text"] == "admin user must enable two-factor authentication"
    assert rows[0]["claims"][0]["claim_group"] == "rule"


def test_global_profile_builder_materializes_relation_claim_text() -> None:
    profile = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="support service",
        entity_type="software",
        normalized_key="support service",
        canonical_key="support service",
        canonical_text="support service | software | uses Freshdesk for customer tickets",
        search_text="support service uses Freshdesk for customer tickets",
        relation_filters={"predicates": ["uses"], "objects": ["Freshdesk for customer tickets"]},
        evidence_refs=[{"claim_ids": ["c-freshdesk"], "sentence_ids": ["s-freshdesk"]}],
    )

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=profile.search_profile_id,
                technical_entity_id=profile.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            )
        ],
        [profile],
    )

    assert rows[0]["claims"][0]["claim_text"] == "support service uses Freshdesk for customer tickets"
    assert rows[0]["claims"][0]["predicate"] == "uses"
    assert rows[0]["claims"][0]["object"] == "Freshdesk for customer tickets"


def test_global_profile_builder_materializes_descriptor_and_event_claims() -> None:
    descriptor = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="Sarah Miller",
        entity_type="person",
        normalized_key="sarah miller",
        canonical_key="miller sarah",
        canonical_text="Sarah Miller | person | is the compliance lead at Acme Corp",
        search_text="Sarah Miller kapcsolatai: is the compliance lead at → Acme Corp.",
        claim_group_signals={"descriptor": 1},
        evidence_refs=[{"claim_ids": ["c-descriptor"], "sentence_ids": ["s-descriptor"]}],
    )
    event = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="billing service",
        entity_type="software",
        normalized_key="billing service",
        canonical_key="billing service",
        canonical_text="billing service | software | was updated in 2025 | 2025",
        search_text="billing service eseményei: was updated → in 2025.",
        claim_group_signals={"event": 1},
        time_filters={"dominant": "historical", "values": ["2025"], "has_historical": True},
        evidence_refs=[{"claim_ids": ["c-event"], "sentence_ids": ["s-event"]}],
    )

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=descriptor.search_profile_id,
                technical_entity_id=descriptor.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            ),
            DecisionAnalysis(
                search_profile_id=event.search_profile_id,
                technical_entity_id=event.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            ),
        ],
        [descriptor, event],
    )

    assert rows[0]["claims"][0]["claim_group"] == "descriptor"
    assert rows[0]["claims"][0]["predicate"] == "is the compliance lead at"
    assert rows[0]["claims"][0]["object"] == "Acme Corp"
    assert rows[1]["claims"][0]["claim_group"] == "event"
    assert rows[1]["claims"][0]["predicate"] == "was updated"
    assert rows[1]["claims"][0]["object"] == "in 2025"


def test_global_profile_builder_materializes_completed_event_with_full_date() -> None:
    profile = SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name="security review",
        entity_type="process",
        normalized_key="security review",
        canonical_key="review security",
        canonical_text="security review | process | was completed on 12 March 2025",
        search_text="security review eseményei: was completed → on 12 March 2025.",
        claim_group_signals={"event": 1},
        time_filters={"dominant": "event", "values": ["March 2025"], "has_historical": True},
        evidence_refs=[{"claim_ids": ["c-completed"], "sentence_ids": ["s-completed"]}],
    )

    rows = GlobalProfileBuilderV0().build_many(
        [
            DecisionAnalysis(
                search_profile_id=profile.search_profile_id,
                technical_entity_id=profile.technical_entity_id,
                decision="create_new_profile",
                decision_type="create_new_profile",
            )
        ],
        [profile],
    )

    claim = rows[0]["claims"][0]
    assert claim["claim_group"] == "event"
    assert claim["predicate"] == "was completed"
    assert claim["object"] == "on 12 March 2025"
    assert claim["claim_text"] == "security review was completed on 12 March 2025"
