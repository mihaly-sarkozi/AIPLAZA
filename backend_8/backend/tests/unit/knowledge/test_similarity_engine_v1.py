from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.domain.similarity_analysis import similarity_analysis_to_json_dict
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1, candidate_selection_attempt_count
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
    canonical_key: str = "",
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


def _has_normalized_name_match(analysis) -> bool:
    return any(reason in {"name:canonical_exact", "name:normalized_key_exact", "name:normalized_exact"} for reason in analysis.similarity_reasons)


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


def test_existing_memory_support_module_spanish_profile_scores_high() -> None:
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
        keywords=["módulo", "soporte", "freshdesk"],
        relation_predicates=["utiliza"],
        relation_objects=["Freshdesk"],
    )

    candidates = CandidateSelectionV1().select_many([new], existing_profiles=[existing], limit_per_profile=3)
    analyses = SimilarityEngineV1().analyze_many([new], candidates, [existing])

    assert candidates
    assert candidates[0].candidate_source == "existing_memory"
    assert analyses
    assert analyses[0].component_scores["name_similarity"] == 1.0
    assert analyses[0].total_similarity_score >= 0.65


def test_similarity_normalized_key_match_without_relation_object_is_capped_below_perfect() -> None:
    existing = _profile("support module", "module", canonical_key="support module", keywords=["support", "module"])
    new = _profile("El módulo de soporte", "module", canonical_key="support module", keywords=["soporte", "módulo"])

    analysis = _analyze(new, existing)

    assert analysis.component_scores["name_similarity"] == 1.0
    assert analysis.component_scores["relation_similarity"] == 0.0
    assert analysis.component_scores["object_similarity"] == 0.0
    assert analysis.total_similarity_score <= 0.85
    assert "missing_relation_object_similarity_cap" in analysis.similarity_reasons


def test_similarity_normalized_key_relation_and_object_match_can_be_near_perfect() -> None:
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

    analysis = _analyze(new, existing)

    assert analysis.component_scores["name_similarity"] == 1.0
    assert analysis.component_scores["relation_similarity"] > 0.0
    assert analysis.component_scores["object_similarity"] > 0.0
    assert analysis.total_similarity_score >= 0.95


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
    assert analysis.component_scores["name_similarity"] == 1.0
    assert analysis.component_scores["keyword_similarity"] > 0
    assert analysis.component_scores["object_similarity"] > 0
    assert _has_normalized_name_match(analysis)


def test_similarity_admin_user_vs_usuario_administrador_is_medium_or_high() -> None:
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

    analysis = _analyze(new, existing)

    assert analysis.similarity_band in {"medium", "high"}
    assert analysis.component_scores["type_similarity"] == 1.0
    assert analysis.component_scores["name_similarity"] == 1.0
    assert _has_normalized_name_match(analysis)
    assert analysis.evidence["claim_ids"]


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
    assert any(reason.startswith("relation_object:normalized_semantic_overlap") for reason in analysis.similarity_reasons)


def test_similarity_predicates_and_objects_are_normalized_cross_language() -> None:
    new = _profile(
        "support module",
        "module",
        keywords=["support", "module"],
        relation_predicates=["uses"],
        relation_objects=["Freshdesk"],
    )
    existing = _profile(
        "support modul",
        "module",
        keywords=["support", "modul"],
        relation_predicates=["használ"],
        relation_objects=["Freshdesk rendszert"],
    )

    analysis = _analyze(new, existing)

    assert analysis.similarity_band == "high"
    assert analysis.total_similarity_score > 0.7
    assert analysis.component_scores["name_similarity"] == 1.0
    assert analysis.component_scores["relation_similarity"] == 1.0
    assert analysis.component_scores["object_similarity"] == 1.0
    assert "relation_predicate:semantic_overlap:1.00" in analysis.similarity_reasons
    assert "relation_object:normalized_semantic_overlap:1.00" in analysis.similarity_reasons


def test_similarity_integrates_with_maps_to_uses_or_integrates_relation_class() -> None:
    new = _profile(
        "support module",
        "module",
        keywords=["support", "module"],
        relation_predicates=["integrates with"],
        relation_objects=["Freshdesk"],
    )
    existing = _profile(
        "módulo de soporte",
        "module",
        keywords=["módulo", "soporte"],
        relation_predicates=["utiliza"],
        relation_objects=["Freshdesk sistema"],
    )

    analysis = _analyze(new, existing)

    assert analysis.total_similarity_score >= 0.65
    assert analysis.component_scores["name_similarity"] == 1.0
    assert analysis.component_scores["relation_similarity"] == 1.0
    assert analysis.component_scores["object_similarity"] == 1.0


def test_similarity_different_type_and_keywords_is_low() -> None:
    new = _profile("billing service", "software", keywords=["billing", "invoice"])
    existing = _profile("Carlos García", "person", keywords=["carlos", "compliance"])

    candidates = CandidateSelectionV1().select_for_profile(new, [existing])
    if not candidates:
        assert candidates == []
        return
    analysis = SimilarityEngineV1().analyze_for_profile(new, candidates, [existing])[0]
    assert analysis.similarity_band == "low"


def test_similarity_random_unrelated_same_type_entities_remain_low() -> None:
    new = _profile("Sarah Miller", "person", keywords=["sarah", "miller", "compliance"])
    existing = _profile("Carlos García", "person", keywords=["carlos", "garcia", "audit"])

    analysis = _analyze(new, existing)

    assert analysis.similarity_band == "low"
    assert analysis.total_similarity_score < 0.4
    assert "structural_only_similarity_cap" in analysis.similarity_reasons


def test_similarity_analysis_contains_component_scores_and_evidence() -> None:
    new = _profile("Sarah Miller", "person", keywords=["sarah", "miller"])
    existing = _profile("Sarah Miller", "person", keywords=["sarah", "miller"])

    analysis = _analyze(new, existing)

    assert set(analysis.component_scores) == {
        "name_similarity",
        "canonical_text_similarity",
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


def test_similarity_legacy_helpdesk_import_vs_regi_helpdesk_import_is_strong_medium_or_high() -> None:
    new = _profile(
        "legacy helpdesk import",
        "module",
        keywords=["legacy", "helpdesk", "import", "deprecated"],
        relation_predicates=["deprecated"],
        relation_objects=["2024"],
        time_values=["2024"],
    )
    existing = _profile(
        "régi Helpdesk import",
        "module",
        keywords=["régi", "helpdesk", "import", "megszűnt"],
        relation_predicates=["megszűnt"],
        relation_objects=["2024"],
        time_values=["2024"],
    )

    analysis = _analyze(new, existing)

    assert analysis.similarity_band == "high"
    assert analysis.total_similarity_score >= 0.75
    assert analysis.component_scores["name_similarity"] == 1.0
    assert _has_normalized_name_match(analysis)
    assert "same_type_strong_lexical_overlap_boost" in analysis.similarity_reasons
    assert analysis.evidence["claim_ids"]


def test_stress_multilingual_data_protection_role_similarity_is_medium_or_high() -> None:
    new = _profile(
        "data protection lead",
        "policy",
        keywords=["data", "protection", "lead", "gdpr"],
        relation_predicates=["responsible"],
    )
    hu = _profile(
        "adatvédelmi felelős",
        "policy",
        keywords=["adatvédelmi", "felelős", "felhasználói", "adatokat"],
        relation_predicates=["kezeli"],
    )
    es = _profile(
        "responsable de protección de datos",
        "policy",
        keywords=["responsable", "protección", "datos", "usuario"],
        relation_predicates=["gestiona"],
    )

    analysis_hu = _analyze(new, hu)
    analysis_es = _analyze(new, es)

    assert analysis_hu.similarity_band in {"medium", "high"}
    assert analysis_es.similarity_band in {"medium", "high"}
    assert _has_normalized_name_match(analysis_hu)
    assert _has_normalized_name_match(analysis_es)


def test_similarity_multilingual_support_module_is_merge_suggestion_strength() -> None:
    new = _profile("support module", "module", keywords=["support", "module"])
    existing_hu = _profile("support modul", "module", keywords=["support", "modul"])
    existing_es = _profile("módulo de soporte", "module", keywords=["módulo", "soporte"])

    analysis_hu = _analyze(new, existing_hu)
    analysis_es = _analyze(new, existing_es)

    assert analysis_hu.similarity_band == "high"
    assert analysis_es.similarity_band == "high"
    assert analysis_hu.total_similarity_score > 0.7
    assert analysis_es.total_similarity_score > 0.7
    assert _has_normalized_name_match(analysis_hu)
    assert _has_normalized_name_match(analysis_es)


@pytest.mark.parametrize(
    ("left", "right", "entity_type"),
    [
        ("support module", "módulo de soporte", "module"),
        ("billing service", "servicio de facturación", "software"),
        ("admin user", "usuario administrador", "user"),
        ("account", "cuenta", "account"),
    ],
)
def test_similarity_canonical_alias_exact_gets_explicit_boost(left: str, right: str, entity_type: str) -> None:
    new = _profile(left, entity_type, keywords=left.split())
    existing = _profile(right, entity_type, keywords=right.split())

    analysis = _analyze(new, existing)

    assert analysis.similarity_band in {"medium", "high"}
    assert analysis.total_similarity_score >= 0.7
    assert _has_normalized_name_match(analysis)
    assert "canonical_alias_similarity_boost" in analysis.similarity_reasons


def test_similarity_explicit_canonical_key_match_is_at_least_medium() -> None:
    new = _profile(
        "legacy helpdesk importer",
        "module",
        keywords=["legacy"],
        canonical_key="legacy helpdesk import",
    )
    existing = _profile(
        "régi Helpdesk import",
        "module",
        keywords=["régi"],
        canonical_key="legacy helpdesk import",
    )

    candidate = CandidateSelectionV1().select_for_profile(new, [existing])[0]
    analysis = SimilarityEngineV1().analyze_for_profile(new, [candidate], [existing])[0]

    assert candidate.score >= 0.55
    assert "canonical_key_match" in " ".join(candidate.reasons)
    assert analysis.similarity_band in {"medium", "high"}
    assert analysis.total_similarity_score >= 0.7
    assert "name:normalized_key_exact" in analysis.similarity_reasons
    assert "normalized_key_similarity_boost" in analysis.similarity_reasons
    assert similarity_analysis_to_json_dict(analysis)["similarity_score"] == analysis.total_similarity_score


def test_candidate_selection_attempts_all_pairs_and_returns_top_canonical_groups() -> None:
    new = _profile("admin user", "user", keywords=["admin", "user"])
    existing = [
        _profile("admin felhasználó", "user", keywords=["admin", "felhasználó"]),
        _profile("usuario administrador", "user", keywords=["usuario", "administrador"]),
        _profile("regular user", "user", keywords=["regular", "user"]),
        _profile("legacy helpdesk import", "module", keywords=["legacy", "helpdesk", "import"]),
    ]

    selector = CandidateSelectionV1()
    candidates = selector.select_for_profile(new, [new, *existing], limit=3)

    assert candidate_selection_attempt_count([new], [new, *existing]) == 4
    assert len(candidates) == 2
    assert candidates[0].score >= candidates[-1].score
    assert candidates[0].score >= 0.5
    assert candidates[0].merge_candidate_group["canonical_key"] == "admin user"
    assert candidates[0].merge_candidate_group["group_size"] == 2
