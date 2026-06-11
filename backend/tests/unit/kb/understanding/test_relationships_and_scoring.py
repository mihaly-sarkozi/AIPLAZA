"""Relationship build és scoring lépések."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.enums.EntityType import EntityType
from apps.kb.kb_understanding.service.BuildRelationshipsService import BuildRelationshipsService
from apps.kb.kb_understanding.service.ScoreKnowledgeService import ScoreKnowledgeService

from tests.unit.kb.understanding.conftest import FakeRelationshipRepository, FakeScoreRepository

pytestmark = pytest.mark.unit


def _entity(name: str, chunk_ids: tuple[str, ...], entity_type=EntityType.PERSON, confidence=0.8):
    return KnowledgeEntityDto(
        entity_type=entity_type,
        name=name,
        normalized_name=name.lower(),
        confidence=confidence,
        chunk_ids=chunk_ids,
    )


def _chunk(chunk_id: str, text: str = "x" * 500, section: str | None = "Szekció"):
    return KnowledgeChunkDto(
        chunk_id=chunk_id,
        text=text,
        chunk_type=ChunkType.TEXT,
        order_index=0,
        token_count=10,
        checksum="abc",
        section_title=section,
    )


def test_relationships_cover_all_edge_types(ctx):
    repo = FakeRelationshipRepository()
    service = BuildRelationshipsService(repo)
    entities = [
        _entity("Kiss Anna", ("chunk_1",)),
        _entity("ACME", ("chunk_1",), entity_type=EntityType.COMPANY),
    ]
    enrichments = [
        KnowledgeEnrichmentDto(chunk_id="chunk_1", topics=("számlázás",), confidence=0.7)
    ]
    count = service.run(ctx, entities, enrichments)
    assert count == len(repo.rows)
    relations = {(row.from_type, row.relation, row.to_type) for row in repo.rows}
    assert ("entity", "mentioned_in", "chunk") in relations
    assert ("entity", "appears_in", "document") in relations
    assert ("entity", "related_to", "entity") in relations
    assert ("topic", "has_topic", "chunk") in relations
    assert ("topic", "has_topic", "document") in relations


def test_cooccurrence_pairs_not_duplicated(ctx):
    repo = FakeRelationshipRepository()
    service = BuildRelationshipsService(repo)
    entities = [
        _entity("Kiss Anna", ("chunk_1", "chunk_2")),
        _entity("ACME", ("chunk_1", "chunk_2"), entity_type=EntityType.COMPANY),
    ]
    service.run(ctx, entities, [])
    related = [row for row in repo.rows if row.relation == "related_to"]
    assert len(related) == 1


def test_scoring_components_and_bounds(ctx):
    repo = FakeScoreRepository()
    service = ScoreKnowledgeService(repo)
    chunks = [_chunk("chunk_1"), _chunk("chunk_2", text="rövid", section=None)]
    entities = [_entity("Kiss Anna", ("chunk_1",))] * 5
    enrichments = [KnowledgeEnrichmentDto(chunk_id="chunk_1", confidence=0.9)]
    scores = service.run(ctx, chunks, entities, enrichments)
    by_chunk = {score.chunk_id: score for score in scores}
    assert set(by_chunk) == {"chunk_1", "chunk_2"}
    rich = by_chunk["chunk_1"]
    poor = by_chunk["chunk_2"]
    assert 0.0 <= poor.knowledge_score < rich.knowledge_score <= 1.0
    assert set(rich.components) == {
        "freshness",
        "structure",
        "source_type",
        "entity_density",
        "length",
        "enrichment_confidence",
    }
    assert rich.components["entity_density"] == 1.0
    assert poor.components["enrichment_confidence"] == 0.0
    assert len(repo.rows) == 2
