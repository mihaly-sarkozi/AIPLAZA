from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.claim import Claim, ClaimType
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster, LocalEntityType
from apps.knowledge.domain.technical_entity import TECHNICAL_ENTITY_BUILDER_VERSION, technical_entity_to_json_dict
from apps.knowledge.service.technical_entity_builder_v1 import TechnicalEntityBuilderV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_technical_entity_builder_groups_claims_and_signatures() -> None:
    run_id = uuid4()
    source_id = uuid4()
    local_id = uuid4()
    c_identity = Claim(
        id=str(uuid4()),
        sentence_id=str(uuid4()),
        subject_text="Login system",
        predicate_text="id",
        object_text="login-system",
        claim_type=ClaimType.IDENTIFIER,
        claim_group="identity",
        confidence=0.9,
    )
    c_state = Claim(
        id=str(uuid4()),
        sentence_id=str(uuid4()),
        subject_text="Login system",
        predicate_text="is active",
        object_text=None,
        claim_type=ClaimType.STATE,
        claim_group="state",
        time_mode="current",
        time_label="currently",
        space_mode="location_independent",
        confidence=0.8,
    )
    c_relation = Claim(
        id=str(uuid4()),
        sentence_id=str(uuid4()),
        subject_text="Login system",
        predicate_text="uses",
        object_text="OpenAI embeddings",
        claim_type=ClaimType.RELATION,
        claim_group="relation",
        confidence=0.85,
    )
    cluster = LocalEntityCluster(
        local_entity_id=local_id,
        run_id=run_id,
        source_id=source_id,
        canonical_name="Login system",
        entity_type=LocalEntityType.SYSTEM,
        normalized_key="login system",
        claim_ids=[c_identity.claim_id, c_state.claim_id, c_relation.claim_id],
        sentence_ids=[c_identity.sentence_id, c_state.sentence_id, c_relation.sentence_id],
        surface_forms=["Login system", "login system"],
        evidence_refs=[],
        confidence=0.82,
        coherence_score=0.91,
    )

    entity = TechnicalEntityBuilderV1().build([cluster], claims=[c_identity, c_state, c_relation])[0]

    assert entity.builder_version == TECHNICAL_ENTITY_BUILDER_VERSION
    assert entity.run_id == run_id
    assert entity.source_id == source_id
    assert entity.local_entity_id == local_id
    assert entity.canonical_name == "Login system"
    assert entity.entity_type == "system"
    assert entity.normalized_key == "login system"
    assert len(entity.identity_claims) == 1
    assert len(entity.state_claims) == 1
    assert len(entity.relation_claims) == 1
    assert set(entity.identity_claims[0]) == {
        "claim_id",
        "sentence_id",
        "predicate",
        "object_text",
        "claim_type",
        "claim_group",
        "confidence",
        "time_mode",
        "time_value",
        "space_mode",
        "space_value",
    }
    assert entity.identity_claims[0]["claim_group"] == "identity"
    assert entity.relation_signature["relation_predicates"] == ["uses"]
    assert entity.relation_signature["relation_objects"] == ["OpenAI embeddings"]
    assert entity.time_signature == {
        "has_current_claims": True,
        "has_historical_claims": False,
        "time_values": ["currently"],
        "dominant_time_mode": "current",
    }
    assert entity.space_signature == {
        "has_bounded_space": False,
        "space_values": [],
        "dominant_space_mode": "irrelevant",
    }
    assert entity.surface_bundle["canonical_name"] == "Login system"
    assert entity.surface_bundle["normalized_key"] == "login system"
    assert entity.surface_bundle["surface_forms"] == ["Login system", "login system"]
    assert entity.surface_bundle["aliases"] == ["Login system", "login system"]
    assert entity.surface_bundle["mention_texts"] == ["Login system", "login system"]
    assert entity.coherence_state == "stable"
    as_json = technical_entity_to_json_dict(entity)
    assert as_json["builder_version"] == TECHNICAL_ENTITY_BUILDER_VERSION
    assert as_json["local_entity_id"] == str(local_id)


def test_technical_entity_builder_uses_cluster_evidence_without_claim_objects() -> None:
    cid = uuid4()
    sid = uuid4()
    cluster = LocalEntityCluster(
        canonical_name="Madrid office",
        entity_type=LocalEntityType.LOCATION,
        normalized_key="madrid office",
        claim_ids=[cid],
        sentence_ids=[sid],
        surface_forms=["Madrid office"],
        evidence_refs=[
            {
                "claim_id": str(cid),
                "sentence_id": str(sid),
                "claim_type": "state",
                "claim_group": "state",
                "confidence": 0.7,
                "predicate": "estaba inactiva",
                "object_text": "en 2024",
                "time_mode": "bounded",
                "time_value": "2024",
                "space_mode": "bounded",
                "space_value": "Madrid",
            }
        ],
        confidence=0.74,
        coherence_score=0.71,
    )

    entity = TechnicalEntityBuilderV1().build([cluster])[0]

    assert entity.state_claims[0]["predicate"] == "estaba inactiva"
    assert entity.space_signature == {
        "has_bounded_space": True,
        "space_values": ["Madrid"],
        "dominant_space_mode": "bounded",
    }
    assert entity.time_signature == {
        "has_current_claims": False,
        "has_historical_claims": True,
        "time_values": ["2024"],
        "dominant_time_mode": "historical",
    }
    assert entity.coherence_state == "uncertain"
    assert entity.surface_bundle["surface_count"] == 1


def test_technical_entity_builder_public_v1_methods() -> None:
    cluster = LocalEntityCluster(
        canonical_name="Search module",
        entity_type=LocalEntityType.MODULE,
        normalized_key="search module",
        surface_forms=["Search module"],
        confidence=0.8,
        coherence_score=0.9,
    )
    builder = TechnicalEntityBuilderV1()

    single = builder.build_from_local_entity(cluster)
    many = builder.build_many([cluster])

    assert single.canonical_name == "Search module"
    assert single.builder_version == TECHNICAL_ENTITY_BUILDER_VERSION
    assert len(many) == 1
    assert many[0].canonical_name == "Search module"
