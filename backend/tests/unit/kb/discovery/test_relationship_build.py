from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto, SpatialMentionDto, TemporalMentionDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.relationships.RelationshipBuildService import RelationshipBuildService

pytestmark = pytest.mark.unit


class _FakeRelRepo:
    def __init__(self) -> None:
        self.rows = []

    def replace_for_job(self, job_id, rows):
        self.rows = rows
        return len(rows)


def test_entity_relationships_built():
    repo = _FakeRelRepo()
    service = RelationshipBuildService(repo)
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
    entities = [
        KnowledgeEntityDto(
            entity_type=EntityType.COMPANY,
            name="ACME Kft.",
            normalized_name="acme kft.",
            confidence=0.9,
            chunk_ids=("c1",),
        ),
        KnowledgeEntityDto(
            entity_type=EntityType.SYSTEM,
            name="HubSpot",
            normalized_name="hubspot",
            confidence=0.9,
            chunk_ids=("c1",),
        ),
    ]
    spatial = [
        SpatialMentionDto(
            chunk_id="c1",
            raw_text="budapesti iroda",
            normalized_location="budapesti iroda",
            location_type="office",
            confidence=0.9,
        )
    ]
    count = service.run(ctx, entities=entities, topics=[], temporal=[], spatial=spatial)
    assert count > 0
    relations = {(r.from_id, r.to_id, r.relation) for r in repo.rows}
    assert ("company:acme kft.", "system:hubspot", "related_to") in relations or any(
        r.relation == "related_to" for r in repo.rows
    )
    assert any(r.relation == "located_at" for r in repo.rows)
