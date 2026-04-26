from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.candidate_selection import EntityCandidate
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.domain.similarity_analysis import SimilarityAnalysis
from apps.knowledge.domain.tension_analysis import TensionAnalysis
from apps.knowledge.service.decision_engine_v1 import DecisionEngineV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profile(name: str, entity_type: str, *, evidence: bool = True) -> SearchProfile:
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
        search_text=f"{name} {entity_type}",
        keywords=name.lower().split(),
        evidence_refs=[{"claim_ids": [claim_id], "sentence_ids": [sentence_id], "source_id": str(uuid4())}]
        if evidence
        else [],
    )


def _candidate(new_profile: SearchProfile, existing: SearchProfile) -> EntityCandidate:
    evidence_ref = (existing.evidence_refs or [{}])[0]
    return EntityCandidate(
        search_profile_id=new_profile.search_profile_id,
        technical_memory_chunk_id=new_profile.technical_memory_chunk_id,
        technical_entity_id=new_profile.technical_entity_id,
        local_entity_id=new_profile.local_entity_id,
        candidate_entity_id=str(existing.technical_entity_id),
        candidate_name=existing.entity_name,
        candidate_type=existing.entity_type,
        candidate_source="existing_memory",
        score=0.8,
        evidence={
            "claim_ids": list(evidence_ref.get("claim_ids") or []),
            "sentence_ids": list(evidence_ref.get("sentence_ids") or []),
            "source_id": evidence_ref.get("source_id"),
        },
    )


def _similarity(new_profile: SearchProfile, candidate: EntityCandidate, band: str, score: float) -> SimilarityAnalysis:
    return SimilarityAnalysis(
        search_profile_id=new_profile.search_profile_id,
        technical_memory_chunk_id=new_profile.technical_memory_chunk_id,
        technical_entity_id=new_profile.technical_entity_id,
        local_entity_id=new_profile.local_entity_id,
        candidate_entity_id=candidate.candidate_entity_id,
        candidate_name=candidate.candidate_name,
        candidate_type=candidate.candidate_type,
        total_similarity_score=score,
        similarity_band=band,
        evidence=dict(candidate.evidence or {}),
    )


def _tension(new_profile: SearchProfile, existing: SearchProfile, band: str, tension_type: str) -> TensionAnalysis:
    return TensionAnalysis(
        search_profile_id_a=new_profile.search_profile_id,
        search_profile_id_b=existing.search_profile_id,
        technical_entity_id_a=new_profile.technical_entity_id,
        technical_entity_id_b=existing.technical_entity_id,
        candidate_name_a=new_profile.entity_name,
        candidate_name_b=existing.entity_name,
        tension_score={"none": 0.0, "low": 0.1, "medium": 0.5, "high": 0.9}[band],
        tension_band=band,
        tension_type=tension_type,
        tension_reasons=[f"{tension_type}:{band}"],
        evidence={
            "claim_ids": ["claim-a", "claim-b"],
            "sentence_ids": ["sentence-a", "sentence-b"],
        },
    )


def test_decision_same_sarah_miller_existing_attach_existing() -> None:
    new = _profile("Sarah Miller", "person")
    existing = _profile("Sarah Miller", "person")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "high", 0.9)
    tension = _tension(new, existing, "low", "duplicate")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision == "attach_existing"
    assert decision.manual_review_required is False
    assert decision.candidate_entity_id == str(existing.technical_entity_id)
    assert decision.affected_claim_ids


def test_decision_london_office_berlin_office_keep_separate() -> None:
    new = _profile("London office", "location")
    existing = _profile("Berlin office", "location")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "low", 0.25)
    tension = _tension(new, existing, "none", "unrelated")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision == "keep_separate"
    assert decision.manual_review_required is False
    assert decision.decision_reason == "keep_separate:different_location_name"


def test_decision_london_current_active_inactive_mark_conflict() -> None:
    new = _profile("London office", "location")
    existing = _profile("London office", "location")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "high", 0.85)
    tension = _tension(new, existing, "high", "contradiction")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision == "mark_conflict"
    assert decision.manual_review_required is True
    assert decision.decision_confidence >= 0.9


def test_decision_admin_multilingual_medium_similarity_needs_review() -> None:
    new = _profile("admin user", "user")
    existing = _profile("admin felhasználó", "user")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "medium", 0.58)
    tension = _tension(new, existing, "low", "additive")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision in {"needs_review", "attach_existing"}
    if decision.decision == "needs_review":
        assert decision.manual_review_required is True


def test_decision_no_candidate_create_new() -> None:
    new = _profile("new onboarding workflow", "process")

    decision = DecisionEngineV1().decide(new)

    assert decision.decision == "create_new"
    assert decision.candidate_entity_id == ""
    assert decision.manual_review_required is False
