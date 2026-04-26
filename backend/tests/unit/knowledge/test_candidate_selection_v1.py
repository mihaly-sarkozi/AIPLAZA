from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1


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
    technical_entity_id=None,
) -> SearchProfile:
    claim_id = str(uuid4())
    sentence_id = str(uuid4())
    return SearchProfile(
        search_profile_id=uuid4(),
        technical_memory_chunk_id=uuid4(),
        technical_entity_id=technical_entity_id or uuid4(),
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


def test_candidate_selection_same_sarah_miller_is_top_candidate() -> None:
    new = _profile(
        "Sarah Miller",
        "person",
        keywords=["sarah", "miller", "compliance", "audit"],
        relation_predicates=["responsible"],
        relation_objects=["internal audit process"],
    )
    sarah = _profile(
        "Sarah Miller",
        "person",
        keywords=["sarah", "miller", "compliance", "audit"],
        relation_predicates=["responsible"],
        relation_objects=["internal audit process"],
    )
    other = _profile("Carlos García", "person", keywords=["carlos", "compliance"])

    candidates = CandidateSelectionV1().select_for_profile(new, [sarah, other])

    assert candidates[0].candidate_name == "Sarah Miller"
    assert candidates[0].score >= 0.8
    assert candidates[0].candidate_source == "existing_memory"
    assert any(reason.startswith("normalized_name_match") for reason in candidates[0].reasons)


def test_candidate_selection_london_vs_berlin_office_is_not_strong_match() -> None:
    new = _profile("London office", "location", keywords=["london", "office", "inactive"], space_values=["London office"])
    berlin = _profile("Berlin office", "location", keywords=["berlin", "office", "active"], space_values=["Berlin office"])

    candidates = CandidateSelectionV1().select_for_profile(new, [berlin])

    assert candidates
    assert candidates[0].score < 0.55


def test_candidate_selection_billing_service_vs_module_is_medium_candidate() -> None:
    new = _profile(
        "billing service",
        "software",
        keywords=["billing", "service", "stripe", "payment", "card"],
        relation_predicates=["uses"],
        relation_objects=["Stripe card payment workflow"],
    )
    module = _profile(
        "billing module",
        "module",
        keywords=["billing", "module", "stripe", "invoice"],
        relation_predicates=["uses"],
        relation_objects=["Stripe invoice workflow"],
    )

    candidates = CandidateSelectionV1().select_for_profile(new, [module])

    assert candidates
    assert 0.45 <= candidates[0].score < 0.8
    assert any(reason.startswith("entity_type_compatible") for reason in candidates[0].reasons)


def test_candidate_selection_admin_user_rule_uses_semantic_object_overlap() -> None:
    new = _profile(
        "admin user",
        "user",
        keywords=["admin"],
        relation_predicates=["must"],
        relation_objects=["enable two-factor authentication"],
    )
    existing = _profile(
        "admin felhasználó",
        "user",
        keywords=["admin"],
        relation_predicates=["kötelező"],
        relation_objects=["kétfaktoros azonosítást használnia"],
    )

    candidates = CandidateSelectionV1().select_for_profile(new, [existing])

    assert candidates
    assert any(reason.startswith("relation_object_semantic_overlap") for reason in candidates[0].reasons)


def test_candidate_selection_admin_user_cross_language_names_are_not_weak_random_candidates() -> None:
    new = _profile(
        "admin user",
        "user",
        keywords=["admin", "user"],
        relation_predicates=["must"],
        relation_objects=["enable two-factor authentication"],
    )
    existing = _profile(
        "usuario administrador",
        "user",
        keywords=["usuario", "administrador"],
        relation_predicates=["debe"],
        relation_objects=["activar autenticación de dos factores"],
    )

    candidates = CandidateSelectionV1().select_for_profile(new, [existing])

    assert candidates
    assert candidates[0].score >= 0.45
    assert any(reason.startswith("canonical_name_match") for reason in candidates[0].reasons)
    assert candidates[0].evidence["claim_ids"]


def test_candidate_selection_batch_fallback_marks_candidate_source() -> None:
    profiles = [
        _profile("Sarah Miller", "person", keywords=["sarah", "miller"]),
        _profile("Sarah Miller", "person", keywords=["sarah", "miller"]),
    ]

    candidates = CandidateSelectionV1().select_many(profiles)

    assert candidates
    assert {candidate.candidate_source for candidate in candidates} == {"batch_fallback"}


def test_candidate_selection_type_mismatch_lowers_score() -> None:
    base = _profile("billing service", "software", keywords=["billing", "service"])
    same_type = _profile("billing service", "software", keywords=["billing", "service"])
    different_type = _profile("billing service", "person", keywords=["billing", "service"])

    same = CandidateSelectionV1().select_for_profile(base, [same_type])[0]
    different = CandidateSelectionV1().select_for_profile(base, [different_type])[0]

    assert different.score < same.score
    assert any(reason.startswith("entity_type_mismatch") for reason in different.reasons)


def test_candidate_selection_rejects_candidate_without_evidence() -> None:
    new = _profile("Sarah Miller", "person", keywords=["sarah", "miller"])
    without_evidence = _profile("Sarah Miller", "person", keywords=["sarah", "miller"], evidence=False)

    candidates = CandidateSelectionV1().select_for_profile(new, [without_evidence])

    assert candidates == []


def test_candidate_selection_deduplicates_same_candidate_entity_id_and_keeps_stronger_reason_set() -> None:
    shared_entity_id = uuid4()
    new = _profile(
        "legacy helpdesk import",
        "module",
        keywords=["legacy", "helpdesk", "import", "deprecated"],
        relation_predicates=["deprecated"],
        relation_objects=["2024"],
    )
    weaker = _profile(
        "helpdesk import",
        "module",
        keywords=["helpdesk", "import"],
        technical_entity_id=shared_entity_id,
    )
    stronger = _profile(
        "legacy helpdesk import",
        "module",
        keywords=["legacy", "helpdesk", "import", "deprecated"],
        relation_predicates=["deprecated"],
        relation_objects=["2024"],
        technical_entity_id=shared_entity_id,
    )

    candidates = CandidateSelectionV1().select_for_profile(new, [weaker, stronger])

    assert len(candidates) == 1
    assert str(candidates[0].candidate_entity_id) == str(shared_entity_id)
    assert candidates[0].candidate_name == "legacy helpdesk import"
    assert any(reason.startswith("normalized_name_match") for reason in candidates[0].reasons)


def test_candidate_selection_legacy_helpdesk_import_matches_regi_helpdesk_import_strongly() -> None:
    new = _profile(
        "legacy helpdesk import",
        "module",
        keywords=["legacy", "helpdesk", "import", "deprecated"],
        relation_predicates=["deprecated"],
        relation_objects=["2024"],
    )
    existing = _profile(
        "régi Helpdesk import",
        "module",
        keywords=["régi", "helpdesk", "import", "megszűnt"],
        relation_predicates=["megszűnt"],
        relation_objects=["2024"],
    )

    candidates = CandidateSelectionV1().select_for_profile(new, [existing])

    assert candidates
    assert candidates[0].score >= 0.65
    assert any(reason.startswith("canonical_name_match") for reason in candidates[0].reasons)
    assert candidates[0].evidence["claim_ids"]
