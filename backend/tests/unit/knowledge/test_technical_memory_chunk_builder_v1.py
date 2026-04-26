from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.technical_entity import TechnicalEntity
from apps.knowledge.domain.technical_memory_chunk import (
    TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION,
    technical_memory_chunk_to_json_dict,
)
from apps.knowledge.service.technical_memory_chunk_builder_v1 import TechnicalMemoryChunkBuilderV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_technical_memory_chunk_builder_flattens_entity_claims_to_facts() -> None:
    run_id = uuid4()
    source_id = uuid4()
    technical_entity_id = uuid4()
    local_entity_id = uuid4()
    relation_claim_id = str(uuid4())
    state_claim_id = str(uuid4())
    relation_sentence_id = str(uuid4())
    state_sentence_id = str(uuid4())
    entity = TechnicalEntity(
        technical_entity_id=technical_entity_id,
        run_id=run_id,
        source_id=source_id,
        local_entity_id=local_entity_id,
        canonical_name="London office",
        entity_type="location",
        normalized_key="london office",
        state_claims=[
            {
                "claim_id": state_claim_id,
                "sentence_id": state_sentence_id,
                "claim_group": "state",
                "claim_type": "state",
                "predicate": "was active",
                "object_text": "before January 2025",
                "confidence": 0.82,
                "time_mode": "bounded",
                "time_value": "before January 2025",
                "space_mode": "bounded",
                "space_value": "London office",
            }
        ],
        relation_claims=[
            {
                "claim_id": relation_claim_id,
                "sentence_id": relation_sentence_id,
                "claim_group": "relation",
                "claim_type": "relation",
                "predicate": "uses",
                "object_text": "badge access",
                "confidence": 0.78,
                "time_mode": "unknown",
                "time_value": None,
                "space_mode": "bounded",
                "space_value": "London office",
            }
        ],
        time_signature={
            "has_current_claims": False,
            "has_historical_claims": True,
            "time_values": ["before January 2025"],
            "dominant_time_mode": "historical",
        },
        space_signature={
            "has_bounded_space": True,
            "space_values": ["London office"],
            "dominant_space_mode": "bounded",
        },
        relation_signature={
            "relation_predicates": ["uses"],
            "relation_objects": ["badge access"],
            "claim_ids": [relation_claim_id],
        },
        evidence_refs=[
            {"claim_id": state_claim_id, "sentence_id": state_sentence_id},
            {"claim_id": relation_claim_id, "sentence_id": relation_sentence_id},
        ],
        coherence_state="stable",
        coherence_score=0.91,
        confidence=0.84,
    )

    chunk = TechnicalMemoryChunkBuilderV1().build_from_technical_entity(entity)

    assert chunk.builder_version == TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION
    assert chunk.run_id == run_id
    assert chunk.source_id == source_id
    assert chunk.technical_entity_id == technical_entity_id
    assert chunk.local_entity_id == local_entity_id
    assert chunk.entity_name == "London office"
    assert chunk.entity_type == "location"
    assert chunk.normalized_key == "london office"
    assert len(chunk.facts) == 2
    assert set(chunk.facts[0]) == {
        "claim_id",
        "sentence_id",
        "claim_group",
        "claim_type",
        "predicate",
        "object_text",
        "confidence",
        "time_mode",
        "time_value",
        "space_mode",
        "space_value",
    }
    fact_by_claim_id = {fact["claim_id"]: fact for fact in chunk.facts}
    assert fact_by_claim_id[state_claim_id]["sentence_id"] == state_sentence_id
    assert fact_by_claim_id[state_claim_id]["time_mode"] == "bounded"
    assert fact_by_claim_id[state_claim_id]["time_value"] == "before January 2025"
    assert fact_by_claim_id[relation_claim_id]["sentence_id"] == relation_sentence_id
    assert chunk.evidence_refs == [
        {"claim_id": state_claim_id, "sentence_id": state_sentence_id},
        {"claim_id": relation_claim_id, "sentence_id": relation_sentence_id},
    ]
    assert chunk.time_profile == {
        "dominant_time_mode": "historical",
        "has_current_claims": False,
        "has_historical_claims": True,
        "time_values": ["before January 2025"],
    }
    assert chunk.space_profile == {
        "dominant_space_mode": "bounded",
        "has_bounded_space": True,
        "space_values": ["London office"],
    }
    assert chunk.relation_profile == {
        "relation_predicates": ["uses"],
        "relation_objects": ["badge access"],
        "relation_count": 1,
    }
    as_json = technical_memory_chunk_to_json_dict(chunk)
    assert as_json["technical_entity_id"] == str(technical_entity_id)
    assert as_json["facts"][0]["claim_id"] in {state_claim_id, relation_claim_id}
    assert chunk.summary_text == "London office kapcsolatai: uses → badge access."


def test_technical_memory_chunk_summary_uses_relation_priority_for_person() -> None:
    leader_claim_id = str(uuid4())
    leader_sentence_id = str(uuid4())
    responsible_claim_id = str(uuid4())
    responsible_sentence_id = str(uuid4())
    entity = TechnicalEntity(
        canonical_name="Kovács Péter",
        entity_type="person",
        relation_claims=[
            {
                "claim_id": leader_claim_id,
                "sentence_id": leader_sentence_id,
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
                "claim_id": responsible_claim_id,
                "sentence_id": responsible_sentence_id,
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
        evidence_refs=[
            {"claim_id": leader_claim_id, "sentence_id": leader_sentence_id},
            {"claim_id": responsible_claim_id, "sentence_id": responsible_sentence_id},
        ],
    )

    chunk = TechnicalMemoryChunkBuilderV1().build_from_technical_entity(entity)

    assert chunk.entity_name == "Kovács Péter"
    assert len(chunk.facts) == 2
    assert "vezetője" in chunk.summary_text
    assert "felelt" in chunk.summary_text
    assert (
        chunk.summary_text
        == "Kovács Péter kapcsolatai: vezetője → Zalka 2000 ügyféltámogatási; felelt → budapesti onboarding folyamatért."
    )
    assert chunk.evidence_refs == [
        {"claim_id": leader_claim_id, "sentence_id": leader_sentence_id},
        {"claim_id": responsible_claim_id, "sentence_id": responsible_sentence_id},
    ]


def test_technical_memory_chunk_summary_uses_rule_when_no_relation() -> None:
    rule_claim_id = str(uuid4())
    rule_sentence_id = str(uuid4())
    entity = TechnicalEntity(
        canonical_name="login rendszer",
        entity_type="system",
        rule_claims=[
            {
                "claim_id": rule_claim_id,
                "sentence_id": rule_sentence_id,
                "claim_group": "rule",
                "claim_type": "rule_procedure",
                "predicate": "igényel",
                "object_text": "kétfaktoros azonosítást",
                "confidence": 0.8,
                "time_mode": "current",
                "time_value": "jelenleg",
                "space_mode": "unknown",
                "space_value": None,
            }
        ],
        relation_signature={
            "relation_predicates": [],
            "relation_objects": [],
            "claim_ids": [],
        },
    )

    chunk = TechnicalMemoryChunkBuilderV1().build_from_technical_entity(entity)

    assert len(chunk.facts) == 1
    assert chunk.facts[0]["claim_group"] == "rule"
    assert chunk.relation_profile["relation_count"] == 0
    assert "igényel" in chunk.summary_text
    assert chunk.summary_text == "login rendszer szabályai: igényel → kétfaktoros azonosítást."


def test_technical_memory_chunk_summary_uses_state_when_no_relation_or_rule() -> None:
    current_claim_id = str(uuid4())
    current_sentence_id = str(uuid4())
    historical_claim_id = str(uuid4())
    historical_sentence_id = str(uuid4())
    entity = TechnicalEntity(
        canonical_name="London office",
        entity_type="location",
        state_claims=[
            {
                "claim_id": current_claim_id,
                "sentence_id": current_sentence_id,
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
                "claim_id": historical_claim_id,
                "sentence_id": historical_sentence_id,
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
        time_signature={
            "dominant_time_mode": "current",
            "has_current_claims": True,
            "has_historical_claims": True,
            "time_values": ["currently", "before January 2025"],
        },
        space_signature={
            "dominant_space_mode": "bounded",
            "has_bounded_space": True,
            "space_values": ["London office"],
        },
    )

    chunk = TechnicalMemoryChunkBuilderV1().build_from_technical_entity(entity)

    assert len(chunk.facts) == 2
    assert chunk.time_profile["has_current_claims"] is True
    assert chunk.time_profile["has_historical_claims"] is True
    assert chunk.space_profile["has_bounded_space"] is True
    assert chunk.summary_text == "London office állapotai: is currently inactive; was active → before January 2025."


def test_technical_memory_chunk_summary_empty_claims() -> None:
    entity = TechnicalEntity(canonical_name="üres entitás", entity_type="system")

    chunk = TechnicalMemoryChunkBuilderV1().build_from_technical_entity(entity)

    assert chunk.summary_text == "üres entitás: nincs aktív claim."


def test_technical_memory_chunk_builder_build_many() -> None:
    first = TechnicalEntity(canonical_name="login rendszer", entity_type="system")
    second = TechnicalEntity(canonical_name="London office", entity_type="location")
    builder = TechnicalMemoryChunkBuilderV1()

    single = builder.build(first)
    chunks = builder.build_many([first, second])

    assert single.entity_name == "login rendszer"
    assert len(chunks) == 2
    assert chunks[0].entity_name == "login rendszer"
    assert chunks[1].entity_name == "London office"
