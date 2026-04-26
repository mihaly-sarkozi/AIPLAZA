from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _profile(
    name: str,
    entity_type: str,
    *,
    keywords: list[str] | None = None,
    relation_predicates: list[str] | None = None,
    relation_objects: list[str] | None = None,
    time_values: list[str] | None = None,
    space_values: list[str] | None = None,
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
            "dominant": "current" if not time_values else "historical",
            "values": time_values or [],
            "has_current": not time_values,
            "has_historical": bool(time_values),
        },
        space_filters={
            "dominant": "bounded" if space_values else "unknown",
            "values": space_values or [],
            "has_bounded": bool(space_values),
        },
        evidence_refs=[{"claim_ids": [claim_id], "sentence_ids": [sentence_id], "source_id": str(uuid4())}]
        if evidence
        else [],
    )


def _analyze(new: SearchProfile, candidate_profile: SearchProfile):
    candidates = CandidateSelectionV1().select_for_profile(new, [candidate_profile])
    assert candidates
    return SimilarityEngineV1().analyze_for_profile(new, candidates, [candidate_profile])[0]


def test_similarity_same_sarah_miller_is_high() -> None:
    new = _profile(
        "Sarah Miller",
        "person",
        keywords=["sarah", "miller", "compliance", "audit"],
        relation_predicates=["responsible"],
        relation_objects=["internal audit process"],
    )
    existing = _profile(
        "Sarah Miller",
        "person",
        keywords=["sarah", "miller", "compliance", "audit"],
        relation_predicates=["responsible"],
        relation_objects=["internal audit process"],
    )

    analysis = _analyze(new, existing)

    assert analysis.similarity_band == "high"
    assert analysis.total_similarity_score >= 0.75
    assert analysis.component_scores["name_similarity"] == 1.0


def test_similarity_london_vs_berlin_office_is_low() -> None:
    new = _profile("London office", "location", keywords=["london", "office", "inactive"], space_values=["London office"])
    existing = _profile("Berlin office", "location", keywords=["berlin", "office", "active"], space_values=["Berlin office"])

    analysis = _analyze(new, existing)

    assert analysis.similarity_band == "low"
    assert analysis.total_similarity_score < 0.4
    assert "location:name_conflict_penalty" in analysis.similarity_reasons


def test_similarity_billing_service_vs_billing_module_is_medium() -> None:
    new = _profile(
        "billing service",
        "software",
        keywords=["billing", "service", "stripe", "payment", "card"],
        relation_predicates=["uses"],
        relation_objects=["Stripe card payment workflow"],
    )
    existing = _profile(
        "billing module",
        "module",
        keywords=["billing", "module", "stripe", "invoice"],
        relation_predicates=["uses"],
        relation_objects=["Stripe invoice workflow"],
    )

    analysis = _analyze(new, existing)

    assert analysis.similarity_band == "medium"
    assert 0.4 <= analysis.total_similarity_score < 0.75
    assert analysis.component_scores["type_similarity"] == pytest.approx(0.65)


def test_similarity_admin_user_vs_admin_felhasznalo_is_medium_or_high() -> None:
    new = _profile(
        "admin user",
        "user",
        keywords=["admin", "user"],
        relation_predicates=["must"],
        relation_objects=["enable two-factor authentication"],
    )
    existing = _profile(
        "admin felhasználó",
        "user",
        keywords=["admin", "felhasználó"],
        relation_predicates=["kötelező"],
        relation_objects=["kétfaktoros azonosítást használnia"],
    )

    analysis = _analyze(new, existing)

    assert analysis.similarity_band in {"medium", "high"}
    assert analysis.component_scores["type_similarity"] == 1.0
    assert analysis.component_scores["keyword_similarity"] > 0
    assert analysis.component_scores["object_similarity"] > 0


def test_similarity_rule_objects_use_semantic_normalized_overlap() -> None:
    new = _profile(
        "admin user",
        "user",
        keywords=["admin", "user", "2fa"],
        relation_predicates=["must"],
        relation_objects=["enable two-factor authentication"],
    )
    existing = _profile(
        "admin felhasználó",
        "user",
        keywords=["admin", "felhasználó", "2fa"],
        relation_predicates=["kötelező"],
        relation_objects=["kétfaktoros azonosítást használnia"],
    )

    analysis = _analyze(new, existing)

    assert analysis.component_scores["object_similarity"] > 0
    assert any(reason.startswith("relation_object:semantic_overlap") for reason in analysis.similarity_reasons)


def test_similarity_different_type_and_keywords_is_low() -> None:
    new = _profile("billing service", "software", keywords=["billing", "invoice"])
    existing = _profile("Carlos García", "person", keywords=["carlos", "compliance"])

    candidates = CandidateSelectionV1().select_for_profile(new, [existing])
    if not candidates:
        assert candidates == []
        return
    analysis = SimilarityEngineV1().analyze_for_profile(new, candidates, [existing])[0]
    assert analysis.similarity_band == "low"


def test_similarity_analysis_contains_component_scores_and_evidence() -> None:
    new = _profile("Sarah Miller", "person", keywords=["sarah", "miller"])
    existing = _profile("Sarah Miller", "person", keywords=["sarah", "miller"])

    analysis = _analyze(new, existing)

    assert set(analysis.component_scores) == {
        "name_similarity",
        "type_similarity",
        "keyword_similarity",
        "relation_similarity",
        "object_similarity",
        "time_similarity",
        "space_similarity",
        "evidence_overlap_similarity",
    }
    assert analysis.evidence["claim_ids"]
    assert analysis.evidence["sentence_ids"]


def test_similarity_type_and_time_space_mode_match_alone_does_not_reach_medium() -> None:
    new = _profile(
        "Payment Core North",
        "module",
        keywords=["north"],
        time_values=["2026"],
        space_values=["Budapest"],
    )
    existing = _profile(
        "Reporting Core South",
        "module",
        keywords=["south"],
        time_values=["2026"],
        space_values=["Budapest"],
    )

    analysis = _analyze(new, existing)

    assert analysis.component_scores["type_similarity"] == 1.0
    assert analysis.component_scores["time_similarity"] == 1.0
    assert analysis.component_scores["space_similarity"] == 1.0
    assert analysis.similarity_band == "low"
    assert analysis.total_similarity_score < 0.4


def test_similarity_candidate_selection_reinput_sarah_miller_high_analysis() -> None:
    existing = _profile(
        "Sarah Miller",
        "person",
        keywords=["sarah", "miller", "compliance", "audit"],
        relation_predicates=["responsible"],
        relation_objects=["internal audit process"],
    )
    new = _profile(
        "Sarah Miller",
        "person",
        keywords=["sarah", "miller", "compliance", "audit"],
        relation_predicates=["responsible"],
        relation_objects=["internal audit process"],
    )

    candidates = CandidateSelectionV1().select_for_profile(new, [existing])
    analyses = SimilarityEngineV1().analyze_for_profile(new, candidates, [existing])

    assert candidates[0].candidate_name == "Sarah Miller"
    assert candidates[0].candidate_source == "existing_memory"
    assert analyses[0].candidate_name == "Sarah Miller"
    assert analyses[0].similarity_band == "high"
    assert analyses[0].component_scores
    assert analyses[0].evidence["claim_ids"]
    assert analyses[0].evidence["sentence_ids"]
    assert "evidence:missing_high_cap" not in analyses[0].similarity_reasons
