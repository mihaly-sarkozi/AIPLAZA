from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeScoringInput
from apps.kb.kb_discovery.scoring.KnowledgeScoringService import KnowledgeScoringService

pytestmark = pytest.mark.unit


class _FakeScoreRepo:
    def replace_for_chunks(self, chunk_ids, scores):
        return len(scores)


def test_knowledge_scoring_produces_components():
    service = KnowledgeScoringService(_FakeScoreRepo())
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
    chunks = [
        DiscoveryChunkDto(
            chunk_id="c1",
            text="ACME Kft. HubSpot",
            chunk_type="paragraph",
            order_index=0,
            section_title="Bevezetés",
        )
    ]
    entities = [
        KnowledgeEntityDto(
            entity_type=EntityType.COMPANY,
            name="ACME Kft.",
            normalized_name="acme kft.",
            confidence=0.9,
            chunk_ids=("c1",),
        )
    ]
    scores = service.run(
        ctx,
        KnowledgeScoringInput(
            chunks=tuple(chunks),
            entities=tuple(entities),
            enrichments=(),
            keywords=(),
            topics=(),
            temporal_mentions=(),
            spatial_mentions=(),
            process_mentions=(),
        ),
    )
    assert len(scores) == 1
    assert scores[0].knowledge_score > 0
    assert "freshness_score" in scores[0].components
