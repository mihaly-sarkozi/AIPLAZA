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
