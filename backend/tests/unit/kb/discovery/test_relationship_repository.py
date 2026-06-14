from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.mapper.discovery_mapper import relationship_dict_to_orm

pytestmark = pytest.mark.unit


def test_relationship_dict_to_orm_persists_evidence_fields():
    ctx = DiscoveryJobContext(
        job_id="disc_job_1",
        understanding_job_id="und_job_1",
        training_item_id="item1",
        training_batch_id="batch1",
        knowledge_base_id="kb1",
        tenant_slug="tenant",
        created_by=1,
        source_type="text",
        title="t",
    )
    row = relationship_dict_to_orm(
        ctx,
        {
            "from_type": "entity",
            "from_id": "company:acme",
            "to_type": "chunk",
            "to_id": "c1",
            "relation": "mentioned_in",
            "evidence_chunk_ids": ["c1"],
            "evidence_text": "ACME Kft.",
            "weight": 0.91,
        },
        builder_name="EntityChunkRelationshipBuilder",
        confidence=0.91,
    )
    assert row.training_item_id == "item1"
    assert row.evidence_chunk_ids == ["c1"]
    assert row.evidence_text == "ACME Kft."
    assert row.weight == 0.91
    assert row.metadata_json["builder"] == "EntityChunkRelationshipBuilder"
