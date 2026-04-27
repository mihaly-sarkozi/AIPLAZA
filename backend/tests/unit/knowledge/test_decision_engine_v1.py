from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.candidate_selection import EntityCandidate
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.domain.similarity_analysis import SimilarityAnalysis
from apps.knowledge.domain.tension_analysis import TensionAnalysis
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1
from apps.knowledge.service.decision_engine_v1 import DecisionEngineV1
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profile(
    name: str,
    entity_type: str,
    *,
    canonical_key: str = "",
    keywords: list[str] | None = None,
    relation_predicates: list[str] | None = None,
    relation_objects: list[str] | None = None,
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
        canonical_key=canonical_key,
        canonical_text=f"{name} | {entity_type}",
        search_text=f"{name} {entity_type} {' '.join(keywords or [])}",
        keywords=keywords or name.lower().split(),
        relation_filters={
            "predicates": relation_predicates or [],
            "objects": relation_objects or [],
        },
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


def _decision_from_candidate_similarity(new: SearchProfile, existing: SearchProfile):
    candidates = CandidateSelectionV1().select_many([new], existing_profiles=[existing], limit_per_profile=3)
    similarities = SimilarityEngineV1().analyze_many([new], candidates, [existing])
    decisions = DecisionEngineV1().decide_many([new], candidates, similarities, tensions=[])
    assert decisions
    return decisions[0]


def _candidate_and_decision_from_similarity(new: SearchProfile, existing: SearchProfile):
    candidates = CandidateSelectionV1().select_many([new], existing_profiles=[existing], limit_per_profile=3)
    similarities = SimilarityEngineV1().analyze_many([new], candidates, [existing])
    decisions = DecisionEngineV1().decide_many([new], candidates, similarities, tensions=[])
    assert candidates
    assert decisions
    return candidates[0], decisions[0]


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
    assert decision.decision_type == "attach_existing"
    assert decision.selected_candidate_id == str(existing.technical_entity_id)
    assert decision.attach_to == str(existing.technical_entity_id)
    assert decision.manual_review_required is False
    assert decision.candidate_entity_id == str(existing.technical_entity_id)
    assert decision.selected_profile_id
    assert decision.created_profile_id is None
    assert decision.affected_claim_ids


def test_decision_london_office_berlin_office_create_new() -> None:
    new = _profile("London office", "location")
    existing = _profile("Berlin office", "location")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "low", 0.25)
    tension = _tension(new, existing, "none", "unrelated")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision == "create_new_profile"
    assert decision.manual_review_required is False
    assert decision.created_profile_id
    assert decision.decision_reason == "create_new_profile:no_candidate_above_threshold"


def test_decision_ignores_tension_and_uses_high_similarity_attach() -> None:
    new = _profile("London office", "location")
    existing = _profile("London office", "location")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "high", 0.85)
    tension = _tension(new, existing, "high", "contradiction")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision == "attach_existing"
    assert decision.manual_review_required is False
    assert decision.decision_reason == "attach_existing:single_high_similarity_candidate"


def test_decision_admin_multilingual_medium_similarity_needs_review() -> None:
    new = _profile("admin user", "user")
    existing = _profile("admin felhasználó", "user")
    candidate = _candidate(new, existing)
    similarity = _similarity(new, candidate, "medium", 0.58)
    tension = _tension(new, existing, "low", "additive")

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity, tension=tension)

    assert decision.decision == "uncertain_match"
    assert decision.manual_review_required is True
    assert decision.decision_reason == "uncertain_match:medium_similarity"


def test_decision_no_candidate_create_new() -> None:
    new = _profile("new onboarding workflow", "process")

    decision = DecisionEngineV1().decide(new)

    assert decision.decision == "create_new_profile"
    assert decision.candidate_entity_id == ""
    assert decision.created_profile_id
    assert decision.manual_review_required is False


def test_decision_multiple_high_similarity_candidates_in_group_merge_required() -> None:
    new = _profile("support module", "module")
    existing = _profile("support module", "module")
    candidate = _candidate(new, existing)
    candidate = EntityCandidate(
        **{
            **candidate.__dict__,
            "merge_candidate_group": {
                "canonical_key": "support module",
                "group_size": 2,
                "duplicate_memory_profile_count": 1,
                "candidate_entity_ids": [candidate.candidate_entity_id, "candidate-2"],
                "selected_candidate_entity_id": candidate.candidate_entity_id,
            },
        }
    )
    similarity = _similarity(new, candidate, "high", 0.92)

    decision = DecisionEngineV1().decide(new, candidate=candidate, similarity=similarity)

    assert decision.decision == "merge_required"
    assert decision.candidate_group_size == 2
    assert decision.competing_candidates_count == 1
    assert decision.merge_candidate_group["canonical_key"] == "support module"


def test_decision_support_module_existing_memory_attach_existing() -> None:
    existing = _profile(
        "support module",
        "module",
        canonical_key="support module",
        keywords=["support", "module", "freshdesk"],
        relation_predicates=["uses"],
        relation_objects=["Freshdesk"],
    )
    new = _profile(
        "El módulo de soporte",
        "module",
        canonical_key="support module",
        keywords=["soporte", "módulo", "freshdesk"],
        relation_predicates=["utiliza"],
        relation_objects=["Freshdesk"],
    )

    candidate, decision = _candidate_and_decision_from_similarity(new, existing)

    assert decision.decision == "attach_existing"
    assert decision.attach_to == str(existing.technical_entity_id)
    assert decision.selected_candidate_score == candidate.score


def test_decision_billing_service_existing_memory_attach_existing() -> None:
    existing = _profile(
        "billing service",
        "software",
        canonical_key="billing service",
        keywords=["billing", "service", "stripe"],
        relation_predicates=["uses"],
        relation_objects=["Stripe"],
    )
    new = _profile(
        "servicio de facturación",
        "software",
        canonical_key="billing service",
        keywords=["servicio", "facturación", "stripe"],
        relation_predicates=["utiliza"],
        relation_objects=["Stripe"],
    )

    candidate, decision = _candidate_and_decision_from_similarity(new, existing)

    assert decision.decision == "attach_existing"
    assert decision.attach_to == str(existing.technical_entity_id)
    assert decision.selected_candidate_score == candidate.score


def test_decision_billing_service_does_not_false_attach_invoice_service() -> None:
    invoice = _profile(
        "invoice service",
        "software",
        canonical_key="invoice service",
        keywords=["invoice", "service", "stripe"],
        relation_predicates=["uses"],
        relation_objects=["Stripe"],
    )
    billing = _profile(
        "billing service",
        "software",
        canonical_key="billing service",
        keywords=["billing", "service", "stripe"],
        relation_predicates=["uses"],
        relation_objects=["Stripe"],
    )

    decision = _decision_from_candidate_similarity(billing, invoice)

    assert decision.decision != "attach_existing"
    assert decision.attach_to is None
