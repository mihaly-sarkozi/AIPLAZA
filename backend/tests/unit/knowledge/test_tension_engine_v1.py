from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.tension_engine_v1 import TensionEngineV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profile(
    name: str,
    entity_type: str,
    *,
    keywords: list[str] | None = None,
    relation_predicates: list[str] | None = None,
    relation_objects: list[str] | None = None,
    time_values: list[str] | None = None,
    has_current: bool | None = None,
    evidence: bool = True,
) -> SearchProfile:
    claim_id = str(uuid4())
    sentence_id = str(uuid4())
    return SearchProfile(
        search_profile_id=uuid4(),
        technical_memory_chunk_id=uuid4(),
        technical_entity_id=uuid4(),
        local_entity_id=uuid4(),
        entity_name=name,
        entity_type=entity_type,
        normalized_key=name.lower(),
        canonical_text=f"{name} | {entity_type}",
        search_text=f"{name} {' '.join(keywords or [])}",
        keywords=keywords or [],
        relation_filters={
            "predicates": relation_predicates or [],
            "objects": relation_objects or [],
        },
        time_filters={
            "dominant": "historical" if time_values else "current",
            "values": time_values or [],
            "has_current": (not time_values) if has_current is None else has_current,
            "has_historical": bool(time_values),
        },
        evidence_refs=[{"claim_ids": [claim_id], "sentence_ids": [sentence_id], "source_id": str(uuid4())}]
        if evidence
        else [],
    )


def test_tension_active_vs_inactive_is_contradiction() -> None:
    profile_a = _profile("London office", "location", keywords=["currently", "active"], relation_predicates=["active"])
    profile_b = _profile("London office", "location", keywords=["currently", "inactive"], relation_predicates=["inactive"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "contradiction"
    assert analysis.tension_band == "high"
    assert analysis.tension_score >= 0.8
    assert analysis.tension_reason.startswith("contradiction:")
    assert "contradiction:opposite_state_same_current_time" in analysis.tension_reasons
    assert analysis.evidence["claim_ids"]
    assert analysis.evidence["sentence_ids"]


def test_tension_different_time_is_temporal_change() -> None:
    profile_a = _profile("London office", "location", keywords=["inactive"], relation_predicates=["inactive"], time_values=["2024"], has_current=False)
    profile_b = _profile("London office", "location", keywords=["currently", "active"], relation_predicates=["active"], has_current=True)

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "temporal_change"
    assert analysis.tension_score < 0.5
    assert analysis.tension_band == "low"


def test_temporal_change_is_not_direct_contradiction() -> None:
    profile_a = _profile(
        "billing system",
        "software",
        relation_predicates=["uses"],
        relation_objects=["manual invoicing"],
        time_values=["2023"],
        has_current=False,
    )
    profile_b = _profile(
        "billing system",
        "software",
        relation_predicates=["uses"],
        relation_objects=["Stripe"],
        time_values=["2025"],
        has_current=False,
    )

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "temporal_change"
    assert analysis.conflict_type == "temporal_change"
    assert analysis.conflict_type != "direct_contradiction"
    assert analysis.conflicting_claim_ids == []


def test_direct_negated_use_is_direct_contradiction() -> None:
    profile_a = _profile(
        "billing system",
        "software",
        relation_predicates=["használ"],
        relation_objects=["Stripe"],
        has_current=True,
    )
    profile_b = _profile(
        "billing system",
        "software",
        relation_predicates=["nem használ"],
        relation_objects=["Stripe"],
        has_current=True,
    )

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "contradiction"
    assert analysis.conflict_type == "direct_contradiction"
    assert analysis.conflicting_claim_ids


def test_tension_same_profile_is_duplicate() -> None:
    profile_a = _profile("Sarah Miller", "person", keywords=["sarah", "miller", "compliance"])
    profile_b = _profile("Sarah Miller", "person", keywords=["sarah", "miller", "compliance"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "duplicate"
    assert analysis.tension_band == "low"


def test_tension_different_entity_is_unrelated() -> None:
    profile_a = _profile("London office", "location", keywords=["london", "office"])
    profile_b = _profile("billing_service", "software", keywords=["billing", "service"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "unrelated"
    assert analysis.tension_score == 0.0
    assert analysis.tension_band == "none"


def test_tension_additive_same_entity_different_facts() -> None:
    profile_a = _profile("Sarah Miller", "person", relation_predicates=["is compliance lead"])
    profile_b = _profile("Sarah Miller", "person", relation_predicates=["was responsible for audit"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "additive"
    assert analysis.tension_band == "low"


def test_tension_contradiction_has_conflicting_claim_ids() -> None:
    profile_a = _profile("London office", "location", relation_predicates=["active"])
    profile_b = _profile("London office", "location", relation_predicates=["inactive"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "contradiction"
    assert analysis.conflicting_claim_ids


def test_tension_hu_kotelezo_vs_nem_kotelezo() -> None:
    profile_a = _profile("admin user", "user", relation_predicates=["kötelező"])
    profile_b = _profile("admin user", "user", relation_predicates=["nem kötelező"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "contradiction"


def test_tension_billing_service_exclusive_current_use_is_medium_or_high() -> None:
    profile_a = _profile(
        "billing service",
        "software",
        relation_predicates=["uses"],
        relation_objects=["Stripe card payments"],
        has_current=True,
    )
    profile_b = _profile(
        "billing service",
        "software",
        relation_predicates=["uses"],
        relation_objects=["manual invoicing"],
        has_current=True,
    )

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "contradiction"
    assert analysis.tension_band in {"medium", "high"}
    assert "contradiction:exclusive_descriptor_object_same_current_time" in analysis.tension_reasons
    assert analysis.conflicting_claim_ids


def test_stress_support_module_multiple_tools_are_additive_not_overwrite() -> None:
    profile_a = _profile(
        "support module",
        "module",
        relation_predicates=["uses"],
        relation_objects=["Zendesk"],
        has_current=True,
    )
    profile_b = _profile(
        "support module",
        "module",
        relation_predicates=["uses"],
        relation_objects=["Freshdesk"],
        has_current=True,
    )

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "additive"
    assert analysis.conflicting_claim_ids == []


def test_stress_london_office_active_then_closed_is_temporal_change() -> None:
    profile_a = _profile(
        "London office",
        "location",
        keywords=["active"],
        relation_predicates=["active"],
        time_values=["before January 2025"],
        has_current=False,
    )
    profile_b = _profile(
        "London office",
        "location",
        keywords=["closed"],
        relation_predicates=["closed"],
        time_values=["February 2025"],
        has_current=False,
    )

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "temporal_change"
    assert analysis.tension_band == "low"
    assert "temporal_change:different_time_values" in analysis.tension_reasons


def test_tension_london_vs_berlin_is_unrelated_or_low_not_contradiction() -> None:
    profile_a = _profile("London office", "location", keywords=["currently", "active"], relation_predicates=["active"])
    profile_b = _profile("Berlin office", "location", keywords=["currently", "inactive"], relation_predicates=["inactive"])

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "unrelated"
    assert analysis.tension_band in {"none", "low"}
    assert analysis.tension_type != "contradiction"


def test_tension_without_evidence_is_not_high() -> None:
    profile_a = _profile("London office", "location", keywords=["currently", "active"], relation_predicates=["active"], evidence=False)
    profile_b = _profile("London office", "location", keywords=["currently", "inactive"], relation_predicates=["inactive"], evidence=False)

    analysis = TensionEngineV1().analyze(profile_a, profile_b)

    assert analysis.tension_type == "contradiction"
    assert analysis.tension_band == "medium"
    assert analysis.tension_score < 0.75
    assert analysis.conflicting_claim_ids == []
    assert analysis.evidence["claim_ids"] == []
    assert analysis.evidence["sentence_ids"] == []


def test_tension_global_profile_update_detects_hard_conflict() -> None:
    profile_update = {
        "profile_id": "global-profile:billing-service",
        "operation": "update",
        "entity_name": "billing service",
        "new_claim_ids": ["new-c"],
        "claims": [
            {
                "claim_id": "old-c",
                "subject": "billing service",
                "predicate": "uses",
                "object": "Stripe",
                "time_dominant": "current",
            },
            {
                "claim_id": "new-c",
                "subject": "billing service",
                "predicate": "uses",
                "object": "manual invoicing",
                "time_dominant": "current",
            },
        ],
    }

    analyses = TensionEngineV1().analyze_global_profiles([profile_update])

    assert len(analyses) == 1
    assert analyses[0].tension_detected is True
    assert analyses[0].tension_type == "hard_conflict"
    assert analyses[0].conflicting_claim_ids == ["old-c", "new-c"]


def test_tension_global_profile_update_detects_temporal_change() -> None:
    profile_update = {
        "profile_id": "global-profile:london-office",
        "operation": "update",
        "entity_name": "London office",
        "new_claim_ids": ["new-c"],
        "claims": [
            {
                "claim_id": "old-c",
                "subject": "London office",
                "predicate": "active",
                "object": "",
                "time_values": ["2024"],
            },
            {
                "claim_id": "new-c",
                "subject": "London office",
                "predicate": "active",
                "object": "",
                "time_values": ["2025"],
            },
        ],
    }

    analyses = TensionEngineV1().analyze_global_profiles([profile_update])

    assert analyses[0].tension_type == "temporal_change"
    assert analyses[0].tension_score > 0


def test_tension_global_profile_update_detects_soft_conflict() -> None:
    profile_update = {
        "profile_id": "global-profile:support-module",
        "operation": "update",
        "entity_name": "support module",
        "new_claim_ids": ["new-c"],
        "claims": [
            {
                "claim_id": "old-c",
                "subject": "support module",
                "predicate": "uses",
                "object": "Freshdesk",
            },
            {
                "claim_id": "new-c",
                "subject": "support module",
                "predicate": "integrates with",
                "object": "Freshdesk",
            },
        ],
    }

    analyses = TensionEngineV1().analyze_global_profiles([profile_update])

    assert analyses[0].tension_type == "soft_conflict"
    assert analyses[0].tension_detected is True
