from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.search_profile import SEARCH_PROFILE_BUILDER_VERSION, search_profile_to_json_dict
from apps.knowledge.domain.technical_memory_chunk import TechnicalMemoryChunk
from apps.knowledge.service.search_profile_builder_v1 import SearchProfileBuilderV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_search_profile_canonical_text_for_person_relations() -> None:
    chunk = TechnicalMemoryChunk(
        technical_memory_chunk_id=uuid4(),
        source_id=uuid4(),
        technical_entity_id=uuid4(),
        local_entity_id=uuid4(),
        entity_name="Kovács Péter",
        entity_type="person",
        normalized_key="kovacs peter",
        summary_text="Kovács Péter kapcsolatai: vezetője → Zalka 2000 ügyféltámogatási; felelt → budapesti onboarding folyamatért.",
        facts=[
            {
                "claim_id": str(uuid4()),
                "sentence_id": str(uuid4()),
                "claim_group": "relation",
                "claim_type": "relation",
                "predicate": "vezetője",
                "object_text": "Zalka 2000 ügyféltámogatási",
                "confidence": 0.8,
                "time_mode": "unknown",
                "time_value": None,
                "space_mode": "unknown",
                "space_value": None,
            },
            {
                "claim_id": str(uuid4()),
                "sentence_id": str(uuid4()),
                "claim_group": "relation",
                "claim_type": "relation",
                "predicate": "felelt",
                "object_text": "budapesti onboarding folyamatért",
                "confidence": 0.8,
                "time_mode": "bounded",
                "time_value": "2025",
                "space_mode": "bounded",
                "space_value": "budapesti",
            },
        ],
        time_profile={
            "dominant_time_mode": "historical",
            "time_values": ["2025"],
            "has_current_claims": False,
            "has_historical_claims": True,
        },
        space_profile={
            "dominant_space_mode": "bounded",
            "space_values": ["budapesti"],
            "has_bounded_space": True,
        },
        relation_profile={"relation_objects": ["Zalka 2000 ügyféltámogatási", "budapesti onboarding folyamatért"]},
        evidence_refs=[{"claim_id": "c1", "sentence_id": "s1"}],
    )

    profile = SearchProfileBuilderV1().build(chunk)

    assert profile.builder_version == SEARCH_PROFILE_BUILDER_VERSION
    assert profile.entity_name == "Kovács Péter"
    assert (
        profile.canonical_text
        == "Kovács Péter | person | vezetője Zalka 2000 ügyféltámogatási | felelt budapesti onboarding folyamatért | 2025 | budapesti"
    )
    assert profile.search_text != profile.canonical_text
    assert "Kovács Péter kapcsolatai" in profile.search_text
    assert "Zalka 2000 ügyféltámogatási" in profile.search_text
    assert "budapesti onboarding folyamatért" in profile.search_text
    assert profile.keywords == [
        "kovács",
        "péter",
        "person",
        "vezetője",
        "zalka",
        "2000",
        "ügyféltámogatási",
        "felelt",
        "budapesti",
        "onboarding",
        "folyamatért",
        "2025",
    ]
    assert len(profile.search_text) <= 1000
    assert profile.aliases == ["Kovács Péter", "kovacs peter"]
    assert profile.claim_group_signals == {
        "relation": 2,
        "state": 0,
        "rule": 0,
        "event": 0,
        "descriptor": 0,
        "other": 0,
    }
    assert profile.time_filters == {
        "dominant": "historical",
        "values": ["2025"],
        "has_current": False,
        "has_historical": True,
    }
    assert profile.space_filters == {
        "dominant": "bounded",
        "values": ["budapesti"],
        "has_bounded": True,
    }
    assert profile.relation_filters == {
        "predicates": ["vezetője", "felelt"],
        "objects": ["Zalka 2000 ügyféltámogatási", "budapesti onboarding folyamatért"],
    }
    assert profile.evidence_refs == [
        {
            "claim_ids": [chunk.facts[0]["claim_id"], chunk.facts[1]["claim_id"], "c1"],
            "sentence_ids": [chunk.facts[0]["sentence_id"], chunk.facts[1]["sentence_id"], "s1"],
            "source_id": str(chunk.source_id),
        }
    ]
    as_json = search_profile_to_json_dict(profile)
    assert as_json["technical_memory_chunk_id"] == str(chunk.technical_memory_chunk_id)


def test_search_profile_canonical_text_for_software_rule() -> None:
    chunk = TechnicalMemoryChunk(
        entity_name="login rendszer",
        entity_type="software",
        normalized_key="login rendszer",
        summary_text="login rendszer szabályai: igényel → kétfaktoros azonosítást.",
        facts=[
            {
                "claim_id": str(uuid4()),
                "sentence_id": str(uuid4()),
                "claim_group": "rule",
                "claim_type": "rule_procedure",
                "predicate": "igényel",
                "object_text": "kétfaktoros azonosítást",
                "confidence": 0.8,
                "time_mode": "current",
                "time_value": "jelenleg",
                "space_mode": "irrelevant",
                "space_value": None,
            }
        ],
        time_profile={
            "dominant_time_mode": "current",
            "time_values": ["jelenleg"],
            "has_current_claims": True,
            "has_historical_claims": False,
        },
        space_profile={
            "dominant_space_mode": "irrelevant",
            "space_values": [],
            "has_bounded_space": False,
        },
    )

    profile = SearchProfileBuilderV1().build(chunk)

    assert profile.canonical_text == "login rendszer | software | igényel kétfaktoros azonosítást | jelenleg"
    assert "login rendszer szabályai" in profile.search_text
    assert "kétfaktoros azonosítást" in profile.search_text
    assert "igényel" in profile.keywords
    assert "jelenleg" not in profile.keywords
    assert len(profile.search_text) <= 1000
    assert profile.aliases == ["login rendszer"]
    assert profile.claim_group_signals == {
        "relation": 0,
        "state": 0,
        "rule": 1,
        "event": 0,
        "descriptor": 0,
        "other": 0,
    }
    assert profile.time_filters == {
        "dominant": "current",
        "values": ["jelenleg"],
        "has_current": True,
        "has_historical": False,
    }
    assert profile.space_filters == {
        "dominant": "irrelevant",
        "values": [],
        "has_bounded": False,
    }
    assert profile.relation_filters == {
        "predicates": [],
        "objects": [],
    }


def test_search_profile_canonical_text_for_location_states() -> None:
    chunk = TechnicalMemoryChunk(
        entity_name="London office",
        entity_type="location",
        normalized_key="london office",
        summary_text="London office állapotai: is currently inactive; was active → before January 2025.",
        facts=[
            {
                "claim_id": str(uuid4()),
                "sentence_id": str(uuid4()),
                "claim_group": "state",
                "claim_type": "state",
                "predicate": "is currently inactive",
                "object_text": None,
                "confidence": 0.8,
                "time_mode": "current",
                "time_value": "currently",
                "space_mode": "bounded",
                "space_value": "London office",
            },
            {
                "claim_id": str(uuid4()),
                "sentence_id": str(uuid4()),
                "claim_group": "state",
                "claim_type": "state",
                "predicate": "was active",
                "object_text": "before January 2025",
                "confidence": 0.8,
                "time_mode": "bounded",
                "time_value": "before January 2025",
                "space_mode": "bounded",
                "space_value": "London office",
            },
        ],
        time_profile={
            "dominant_time_mode": "current",
            "time_values": ["currently", "before January 2025"],
            "has_current_claims": True,
            "has_historical_claims": True,
        },
        space_profile={
            "dominant_space_mode": "bounded",
            "space_values": ["London office"],
            "has_bounded_space": True,
        },
    )

    profile = SearchProfileBuilderV1().build(chunk)

    assert (
        profile.canonical_text
        == "London office | location | currently inactive | active before January 2025 | London office"
    )
    assert "London office állapotai" in profile.search_text
    assert "before January 2025" in profile.search_text
    assert "inactive" in profile.keywords
    assert "currently" not in profile.keywords
    assert "before" not in profile.keywords
    assert len(profile.search_text) <= 1000
    assert profile.aliases == ["London office", "london office"]
    assert profile.claim_group_signals == {
        "relation": 0,
        "state": 2,
        "rule": 0,
        "event": 0,
        "descriptor": 0,
        "other": 0,
    }
    assert profile.time_filters == {
        "dominant": "current",
        "values": ["currently", "before January 2025"],
        "has_current": True,
        "has_historical": True,
    }
    assert profile.space_filters == {
        "dominant": "bounded",
        "values": ["London office"],
        "has_bounded": True,
    }
    assert profile.relation_filters == {
        "predicates": [],
        "objects": [],
    }


def test_search_profile_build_many_preserves_order() -> None:
    first = TechnicalMemoryChunk(entity_name="first", entity_type="system")
    second = TechnicalMemoryChunk(entity_name="second", entity_type="system")

    profiles = SearchProfileBuilderV1().build_many([first, second])

    assert [item.entity_name for item in profiles] == ["first", "second"]
