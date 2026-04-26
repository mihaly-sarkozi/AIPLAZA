from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1


pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


def _profile(
    name: str,
    entity_type: str,
    *,
    keywords: list[str],
    relation_predicates: list[str],
    relation_objects: list[str],
) -> SearchProfile:
    return SearchProfile(
        search_profile_id=uuid4(),
        technical_memory_chunk_id=uuid4(),
        technical_entity_id=uuid4(),
        local_entity_id=uuid4(),
        entity_name=name,
        entity_type=entity_type,
        normalized_key=name.lower(),
        canonical_text=f"{name} | {' '.join(relation_objects)}",
        search_text=f"{name} {' '.join(keywords)} {' '.join(relation_objects)}",
        keywords=keywords,
        relation_filters={
            "predicates": relation_predicates,
            "objects": relation_objects,
        },
        time_filters={
            "dominant": "current",
            "values": [],
            "has_current": True,
            "has_historical": False,
        },
        space_filters={
            "dominant": "unknown",
            "values": [],
            "has_bounded": False,
        },
        evidence_refs=[
            {
                "claim_ids": [str(uuid4())],
                "sentence_ids": [str(uuid4())],
                "source_id": str(uuid4()),
            }
        ],
    )


def test_same_name_existing_memory_sarah_miller_reinput_is_high_similarity() -> None:
    existing_memory = _profile(
        "Sarah Miller",
        "person",
        keywords=["Sarah Miller", "data protection", "Zalka 2000", "incident handling"],
        relation_predicates=["is", "responsible"],
        relation_objects=[
            "data protection lead at Zalka 2000",
            "internal incident handling process",
        ],
    )
    new_input = _profile(
        "Sarah Miller",
        "person",
        keywords=["Sarah Miller", "data protection", "Zalka 2000"],
        relation_predicates=["is"],
        relation_objects=["data protection lead at Zalka 2000"],
    )

    candidates = CandidateSelectionV1().select_many([new_input], [existing_memory])
    analyses = SimilarityEngineV1().analyze_for_profile(new_input, candidates, [existing_memory])

    assert candidates
    assert candidates[0].candidate_source == "existing_memory"
    assert candidates[0].candidate_name == "Sarah Miller"
    assert analyses
    assert analyses[0].candidate_name == "Sarah Miller"
    assert analyses[0].total_similarity_score >= 0.75
    assert analyses[0].similarity_band == "high"
    assert "same_entity_name_boost" in analyses[0].similarity_reasons
    assert "type:match" in analyses[0].similarity_reasons
