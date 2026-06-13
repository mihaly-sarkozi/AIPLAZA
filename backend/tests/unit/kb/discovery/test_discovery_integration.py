"""Integrációs teszt: mintamondat felismerése regex/dictionary recognizer-ekkel."""
from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.entities.CompanyNameRecognizer import CompanyNameRecognizer
from apps.kb.kb_discovery.entities.DictionaryEntityRecognizer import SystemNameRecognizer
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.keywords.KeywordExtractionService import KeywordExtractionService
from apps.kb.kb_discovery.relationships.RelationshipBuildService import RelationshipBuildService
from apps.kb.kb_discovery.entities.EntityRecognitionService import EntityRecognitionService
from apps.kb.kb_discovery.spatial.LocationRecognizer import LocationRecognizer
from apps.kb.kb_discovery.temporal.DateRecognizer import DateRecognizer
from apps.kb.kb_discovery.topics.TopicDetectionService import TopicDetectionService

pytestmark = pytest.mark.unit

SAMPLE = "Az ACME Kft. 2026. július 1-től a budapesti irodában HubSpotot használ."


class _FakeRepo:
    def replace_for_job(self, *_args, **_kwargs):
        return 0

    def replace_for_document(self, *_args, **_kwargs):
        return 0

    def replace_for_chunks(self, *_args, **_kwargs):
        return 0


def _chunk() -> DiscoveryChunkDto:
    return DiscoveryChunkDto(
        chunk_id="c1",
        text=SAMPLE,
        chunk_type="paragraph",
        order_index=0,
    )


def _ctx() -> DiscoveryJobContext:
    return DiscoveryJobContext(
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


def test_full_sentence_company_system_temporal_spatial():
    chunks = [_chunk()]
    context = DiscoveryContext(
        tenant_slug="tenant",
        knowledge_base_id="kb1",
        training_item_id="item1",
    )

    companies = CompanyNameRecognizer().recognize(chunks, context)
    systems = SystemNameRecognizer().recognize(chunks, context)
    temporal = DateRecognizer().recognize(chunks[0])
    spatial = LocationRecognizer().recognize(SAMPLE)

    assert any(c.entity_type == EntityType.COMPANY and "ACME" in c.name for c in companies)
    assert any(s.entity_type == EntityType.SYSTEM for s in systems)
    assert any(t.get("normalized_start") == "2026-07-01" for t in temporal)
    assert any("irod" in m["raw_text"].lower() for m in spatial)


def test_full_sentence_keywords_topics_relationships():
    ctx = _ctx()
    chunks = [_chunk()]

    entity_service = EntityRecognitionService(_FakeRepo(), _FakeRepo())
    entities, _ = entity_service.run(ctx, chunks)

    keywords = KeywordExtractionService(_FakeRepo()).run(ctx, chunks)
    topics = TopicDetectionService(_FakeRepo()).run(ctx, chunks)

    from apps.kb.kb_discovery.spatial.SpatialExtractionService import SpatialExtractionService
    from apps.kb.kb_discovery.temporal.TemporalExtractionService import TemporalExtractionService

    temporal = TemporalExtractionService(_FakeRepo()).run(ctx, chunks)
    spatial = SpatialExtractionService(_FakeRepo()).run(ctx, chunks)

    rel_repo = _FakeRepo()
    rel_repo.rows = []

    class _RelRepo(_FakeRepo):
        def replace_for_job(self, job_id, rows):
            self.rows = rows
            return len(rows)

    repo = _RelRepo()
    RelationshipBuildService(repo).run(
        ctx,
        entities=entities,
        topics=topics,
        temporal=temporal,
        spatial=spatial,
    )

    terms = {k.term.lower() for k in keywords}
    assert any("acme" in t or "hubspot" in t for t in terms)
    assert any(t.topic_key == "sales" for t in topics)
    assert len(repo.rows) > 0
